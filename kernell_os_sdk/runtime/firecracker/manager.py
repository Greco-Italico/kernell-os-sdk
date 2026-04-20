import subprocess
import uuid
import os
import time
import httpx

class FirecrackerManager:
    """
    Manager to orchestrate Firecracker MicroVMs.
    Handles VM lifecycle: start, configure API socket, and cleanup.
    """

    def __init__(self, kernel_path: str, rootfs_path: str):
        self.kernel = kernel_path
        self.rootfs = rootfs_path

    def start_vm(self, memory_mb=128, cpu_count=1):
        vm_id = str(uuid.uuid4())
        socket_path = f"/tmp/firecracker-{vm_id}.sock"

        # 1. Start firecracker process
        process = subprocess.Popen(
            ["firecracker", "--api-sock", socket_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # Wait for socket to be ready
        for _ in range(10):
            if os.path.exists(socket_path):
                break
            time.sleep(0.05)

        client = httpx.Client(transport=httpx.HTTPTransport(uds=socket_path), timeout=2.0)

        try:
            # 2. Configure Machine
            client.put("http://localhost/machine-config", json={
                "vcpu_count": cpu_count,
                "mem_size_mib": memory_mb
            }).raise_for_status()

            # 3. Configure Boot Source
            client.put("http://localhost/boot-source", json={
                "kernel_image_path": self.kernel,
                "boot_args": "console=ttyS0 reboot=k panic=1 pci=off"
            }).raise_for_status()

            # 4. Configure Drives
            client.put("http://localhost/drives/rootfs", json={
                "drive_id": "rootfs",
                "path_on_host": self.rootfs,
                "is_root_device": True,
                "is_read_only": False
            }).raise_for_status()

            # 4.5 Configure VSOCK
            client.put("http://localhost/vsock", json={
                "vsock_id": "vsock0",
                "guest_cid": 3,
                "uds_path": f"/tmp/vsock-{vm_id}.sock"
            }).raise_for_status()

            # 5. Start Instance
            client.put("http://localhost/actions", json={
                "action_type": "InstanceStart"
            }).raise_for_status()

        except Exception as e:
            process.kill()
            if os.path.exists(socket_path):
                os.remove(socket_path)
            raise RuntimeError(f"Failed to configure Firecracker VM: {e}")

    def wait_until_ready(self, process: subprocess.Popen, timeout=5.0):
        deadline = time.monotonic() + timeout
        for line in iter(process.stdout.readline, ""):
            if time.monotonic() > deadline:
                raise TimeoutError("VM did not reach VM_READY state in time")
            if "[VM_READY]" in line:
                return

    def create_snapshot(self, socket_path: str, vm_id: str, snapshot_dir: str):
        snap_path = os.path.join(snapshot_dir, f"{vm_id}.snap")
        mem_path = os.path.join(snapshot_dir, f"{vm_id}.mem")
        
        client = httpx.Client(transport=httpx.HTTPTransport(uds=socket_path), timeout=2.0)
        client.put("http://localhost/snapshot/create", json={
            "snapshot_type": "Full",
            "snapshot_path": snap_path,
            "mem_file_path": mem_path
        }).raise_for_status()
        
        return snap_path, mem_path

    def restore_snapshot(self, snap_path: str, mem_path: str):
        vm_id = str(uuid.uuid4())
        socket_path = f"/tmp/firecracker-{vm_id}.sock"

        process = subprocess.Popen(
            ["firecracker", "--api-sock", socket_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        for _ in range(20):
            if os.path.exists(socket_path):
                break
            time.sleep(0.05)

        client = httpx.Client(transport=httpx.HTTPTransport(uds=socket_path), timeout=2.0)
        
        try:
            client.put("http://localhost/snapshot/load", json={
                "snapshot_path": snap_path,
                "mem_file_path": mem_path,
                "enable_diff_snapshots": False
            }).raise_for_status()
            
            client.put("http://localhost/actions", json={
                "action_type": "Resume"
            }).raise_for_status()
        except Exception as e:
            process.kill()
            if os.path.exists(socket_path):
                os.remove(socket_path)
            raise RuntimeError(f"Failed to restore Firecracker VM: {e}")

        return vm_id, socket_path, process

    def cleanup_vm(self, vm_id: str, socket_path: str, process: subprocess.Popen):
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            
        if os.path.exists(socket_path):
            os.remove(socket_path)
