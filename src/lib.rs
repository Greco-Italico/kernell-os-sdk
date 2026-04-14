use pyo3::prelude::*;

mod wal;
mod engine;

/// A Python module implemented in Rust.
#[pymodule]
fn kap_core(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_class::<wal::RustTransactionWAL>()?;
    m.add_class::<engine::RustEscrowEngine>()?;
    Ok(())
}
