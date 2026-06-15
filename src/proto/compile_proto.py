import sys
import subprocess
import os

def compile_and_strip():
    proto_dir = os.path.dirname(os.path.abspath(__file__))
    proto_file = os.path.join(proto_dir, "simulation.proto")
    cmd = [
        sys.executable,
        "-m",
        "grpc_tools.protoc",
        f"-I{proto_dir}",
        f"--python_out={proto_dir}",
        f"--grpc_python_out={proto_dir}",
        proto_file
    ]
    subprocess.run(cmd, check=True)
    
    pb2_path = os.path.join(proto_dir, "simulation_pb2.py")
    pb2_grpc_path = os.path.join(proto_dir, "simulation_pb2_grpc.py")
    
    for path in [pb2_path, pb2_grpc_path]:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            stripped_lines = [line for line in lines if not line.strip().startswith("#")]
            with open(path, "w", encoding="utf-8") as f:
                f.writelines(stripped_lines)

if __name__ == "__main__":
    compile_and_strip()
