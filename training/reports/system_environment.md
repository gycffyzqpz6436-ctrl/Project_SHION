# System environment — measured 2026-08-09 JST

| Component | Version / value | Status | Detection command | Notes |
|---|---|---|---|---|
| CPU | Intel Core Ultra 7 265KF; 20 physical / 20 logical | Ready | `Get-CimInstance Win32_Processor` | Owner value confirmed |
| GPU | NVIDIA GeForce RTX 5070 | Ready | `nvidia-smi` / PyTorch | Compute Capability 12.0 (`sm_120`) |
| VRAM | 12,227 MiB total; 11,165 MiB free at inspection | Ready | `nvidia-smi --query-gpu` | GDDR7 per Owner |
| BF16 | Supported | Ready | `torch.cuda.is_bf16_supported()` | CUDA BF16 test passed |
| RAM | 33,166,204 KiB visible (~31.63 GiB) | Ready | `Win32_OperatingSystem` | ~20.1 GiB free during inspection |
| C: | 999.2 GB; 685.6 GB free before environment build | Ready | `Win32_LogicalDisk` | NTFS, repository and venv |
| D: | 500.1 GB; 209.55 GB free after model download | Ready | `Win32_LogicalDisk` | NTFS, models and outputs |
| Windows | Windows 11 Home, 64-bit, build 26200 | Ready | `Win32_OperatingSystem` | `Get-ComputerInfo` reports legacy version label 2009 |
| NVIDIA Driver | 591.74 | Ready | `nvidia-smi` | WDDM |
| Driver CUDA | 13.1 | Ready | `nvidia-smi` | Maximum driver-supported CUDA |
| CUDA Toolkit | 12.8.61 | Ready | `nvcc --version` | Matches PyTorch cu128 family |
| WSL | Not installed | Not selected | `wsl --version/status/list` | No distribution; passthrough unavailable until OS install |
| Python (system) | 3.10.6 | Present | `python --version` | Packages not installed globally |
| Python venv | `training/.venv`, Python 3.10.6 | Ready | venv Python | Gitignored |
| pip | 26.2.1 in venv | Ready | `python -m pip --version` | Isolated |
| Git | 2.50.1.windows.1 | Ready | `git --version` |  |
| Git LFS | 3.7.0 | Ready | `git lfs version` | Models not stored in Git/LFS |
| PyTorch | 2.11.0+cu128 | Ready | Python import | GPU `sm_120`, BF16 passed |
| Transformers | 5.14.1 | Ready | Python import | Required for `ministral3` inner config |
| PEFT | 0.20.0 | Ready | Python import | In-memory adapter injection still validated separately |
| TRL | 1.9.2 | Installed fallback | Python import | Automatic assistant mask unsuitable for official template |
| bitsandbytes | 0.50.0 | Ready | CUDA NF4 roundtrip | Windows `sm_120` wheel works |
| accelerate | 1.14.0 | Ready | Python import |  |
| datasets | 4.8.5 | Ready | Python import |  |
| safetensors | 0.8.0 | Ready | Python import |  |
| sentencepiece | 0.2.2 | Ready | Python import |  |
| huggingface_hub | 1.27.0 | Ready | Python import | No token stored in repository |
| PyYAML | 6.0.3 | Ready | Python import |  |
| pytest | 9.1.1 | Ready | Python import |  |
| Unsloth | Not installed | Optional / not selected | package inspection | Avoided for reproducibility and native compatibility risk |
| CMake | Not found | Not required now | `cmake --version` | Needed only for source builds / some future GGUF flows |
| Ninja | Not found | Not required now | `ninja --version` |  |
| Visual C++ Build Tools | `cl.exe` not found | Not required now | `where cl` | Prebuilt wheels used |
| llama.cpp | Not found | Future | `where llama-cli` | Install only for future GGUF/runtime work |

The NVIDIA Driver reports CUDA 13.1 while PyTorch bundles CUDA 12.8 runtime;
this is expected and compatible because the driver is newer than the runtime.

