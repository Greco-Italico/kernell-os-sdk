use pyo3::prelude::*;
use pyo3::types::{PyDict, PyAny};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::fs::{File, OpenOptions};
use std::io::{Read, Write};
use std::path::Path;
use sha2::{Sha256, Digest};
use std::time::{SystemTime, UNIX_EPOCH};

const GENESIS_HASH: &str = "kap:wal:genesis:v1";

#[derive(Serialize, Deserialize)]
struct WalEntry {
    seq: u64,
    ts: f64,
    prev_hash: String,
    data: Value,
    hash: String,
}

#[pyclass]
pub struct RustTransactionWAL {
    path: String,
    last_hash: String,
    seq: u64,
}

#[pymethods]
impl RustTransactionWAL {
    #[new]
    pub fn new(path: &str) -> PyResult<Self> {
        let mut wal = RustTransactionWAL {
            path: path.to_string(),
            last_hash: get_genesis_hash(),
            seq: 0,
        };
        wal.recover_state();
        Ok(wal)
    }

    pub fn append(&mut self, py: Python, record_dict: &PyDict) -> PyResult<PyObject> {
        self.seq += 1;
        let ts = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_secs_f64();
        
        // Convert PyDict to serde_json::Value
        let json_str: String = py.import("json")?.call_method1("dumps", (record_dict,))?.extract()?;
        let data: Value = serde_json::from_str(&json_str).unwrap();

        let mut entry = WalEntry {
            seq: self.seq,
            ts,
            prev_hash: self.last_hash.clone(),
            data,
            hash: String::new(),
        };

        // Custom canonical JSON hashing for compatibility for now, or pure bincode hashing?
        // Since it's a Rust rewrite, we can use bincode hash!
        // But to keep it "append-only zero-copy", we serialize the entry without hash first.
        let bytes_to_hash = bincode::serialize(&(&entry.seq, &entry.ts, &entry.prev_hash, &entry.data)).unwrap();
        let mut hasher = Sha256::new();
        hasher.update(&bytes_to_hash);
        entry.hash = hex::encode(hasher.finalize());

        self.last_hash = entry.hash.clone();

        // Write as binary using bincode length-prefixed
        let out_bytes = bincode::serialize(&entry).unwrap();
        
        // Length prefix (8 bytes)
        let len_prefix = (out_bytes.len() as u64).to_le_bytes();
        
        let mut file = OpenOptions::new().create(true).append(true).open(&self.path)?;
        file.write_all(&len_prefix)?;
        file.write_all(&out_bytes)?;
        file.sync_all()?; // Equivalent to os.fsync

        // Return the entry as a PyDict
        let py_dict = PyDict::new(py);
        py_dict.set_item("seq", self.seq)?;
        py_dict.set_item("ts", ts)?;
        py_dict.set_item("prev_hash", &entry.prev_hash)?;
        py_dict.set_item("hash", &entry.hash)?;
        
        let json_data = serde_json::to_string(&entry.data).unwrap();
        let py_data_dict = py.import("json")?.call_method1("loads", (json_data,))?;
        py_dict.set_item("data", py_data_dict)?;

        Ok(py_dict.into())
    }

    fn verify_integrity(&self) -> PyResult<(bool, u64)> {
        let mut prev_hash = get_genesis_hash();
        let mut checked = 0;

        if let Ok(mut file) = File::open(&self.path) {
            loop {
                let mut len_buf = [0u8; 8];
                if file.read_exact(&mut len_buf).is_err() {
                    break;
                }
                let len = u64::from_le_bytes(len_buf) as usize;
                let mut data_buf = vec![0u8; len];
                if file.read_exact(&mut data_buf).is_err() {
                    break;
                }
                if let Ok(entry) = bincode::deserialize::<WalEntry>(&data_buf) {
                    if entry.prev_hash != prev_hash {
                        return Ok((false, checked));
                    }
                    let bytes_to_hash = bincode::serialize(&(&entry.seq, &entry.ts, &entry.prev_hash, &entry.data)).unwrap();
                    let mut hasher = Sha256::new();
                    hasher.update(&bytes_to_hash);
                    let expected_hash = hex::encode(hasher.finalize());

                    if entry.hash != expected_hash {
                        return Ok((false, checked));
                    }
                    prev_hash = entry.hash;
                    checked += 1;
                } else {
                    return Ok((false, checked));
                }
            }
        }
        Ok((true, checked))
    }

    #[pyo3(signature = (since_seq=0))]
    fn replay(&self, py: Python, since_seq: u64) -> PyResult<Vec<PyObject>> {
        let mut entries = Vec::new();
        if let Ok(mut file) = File::open(&self.path) {
            loop {
                let mut len_buf = [0u8; 8];
                if file.read_exact(&mut len_buf).is_err() {
                    break;
                }
                let len = u64::from_le_bytes(len_buf) as usize;
                let mut data_buf = vec![0u8; len];
                if file.read_exact(&mut data_buf).is_err() {
                    break;
                }
                if let Ok(entry) = bincode::deserialize::<WalEntry>(&data_buf) {
                    if entry.seq > since_seq {
                        let py_dict = PyDict::new(py);
                        py_dict.set_item("seq", entry.seq)?;
                        py_dict.set_item("ts", entry.ts)?;
                        py_dict.set_item("prev_hash", &entry.prev_hash)?;
                        py_dict.set_item("hash", &entry.hash)?;
                        let json_data = serde_json::to_string(&entry.data).unwrap();
                        let py_data_dict = py.import("json")?.call_method1("loads", (json_data,))?;
                        py_dict.set_item("data", py_data_dict)?;
                        entries.push(py_dict.into());
                    }
                } else {
                    break;
                }
            }
        }
        Ok(entries)
    }
}

impl RustTransactionWAL {
    fn recover_state(&mut self) {
        if let Ok(mut file) = File::open(&self.path) {
            let mut last_entry: Option<WalEntry> = None;
            loop {
                let mut len_buf = [0u8; 8];
                if file.read_exact(&mut len_buf).is_err() {
                    break;
                }
                let len = u64::from_le_bytes(len_buf) as usize;
                let mut data_buf = vec![0u8; len];
                if file.read_exact(&mut data_buf).is_err() {
                    break;
                }
                if let Ok(entry) = bincode::deserialize::<WalEntry>(&data_buf) {
                    last_entry = Some(entry);
                } else {
                    break;
                }
            }
            if let Some(entry) = last_entry {
                self.seq = entry.seq;
                self.last_hash = entry.hash;
            }
        }
    }
}

fn get_genesis_hash() -> String {
    let mut hasher = Sha256::new();
    hasher.update(GENESIS_HASH.as_bytes());
    hex::encode(hasher.finalize())
}
