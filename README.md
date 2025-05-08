# blockdownload
A tool that downloads large files in parallel chunks and reassembles them - perfect for improving download speeds and handling interruptions.


[![pypi](https://img.shields.io/pypi/pyversions/blockdownload)](https://pypi.org/project/blockdownload/)
[![Github Actions Build](https://github.com/WolfgangFahl/blockdownload/actions/workflows/build.yml/badge.svg)](https://github.com/WolfgangFahl/blockdownload/actions/workflows/build.yml)
[![PyPI Status](https://img.shields.io/pypi/v/blockdownload.svg)](https://pypi.python.org/pypi/blockdownload/)
[![GitHub issues](https://img.shields.io/github/issues/WolfgangFahl/blockdownload.svg)](https://github.com/WolfgangFahl/blockdownload/issues)
[![GitHub closed issues](https://img.shields.io/github/issues-closed/WolfgangFahl/blockdownload.svg)](https://github.com/WolfgangFahl/blockdownload/issues/?q=is%3Aissue+is%3Aclosed)
[![API Docs](https://img.shields.io/badge/API-Documentation-blue)](https://WolfgangFahl.github.io/blockdownload/)
[![License](https://img.shields.io/github/license/WolfgangFahl/blockdownload.svg)](https://www.apache.org/licenses/LICENSE-2.0)


## Overview

`blockdownload` is a Python-based utility that divides large file downloads into smaller, manageable blocks. This approach offers several advantages:

- **Parallel downloading**: Download multiple blocks simultaneously for improved speed
- **Resume capability**: Continue interrupted downloads without starting over
- **Integrity verification**: MD5 checksums for each block ensure data integrity
- **Cross-platform**: Works on Linux, macOS, and potentially other platforms

### Documentation

[Wiki](http://wiki.bitplan.com/index.php/blockdownload)

### Usage
```bash
usage: blockdownload [-h] --name NAME [--blocksize BLOCKSIZE]
                     [--unit {KB,MB,GB}] [--from-block FROM_BLOCK]
                     [--to-block TO_BLOCK] [--boost BOOST] [--progress]
                     [--yaml YAML] [--force] [--output OUTPUT]
                     url target

Segmented file downloader using HTTP range requests.

positional arguments:
  url                   URL to download from
  target                Target directory to store .part files

options:
  -h, --help            show this help message and exit
  --name NAME           Name for the download session (used for .yaml control
                        file)
  --blocksize BLOCKSIZE
                        Block size (default: 10)
  --unit {KB,MB,GB}     Block size unit (default: MB)
  --from-block FROM_BLOCK
                        First block index
  --to-block TO_BLOCK   Last block index (inclusive)
  --boost BOOST         Number of concurrent download threads (default: 1)
  --progress            Show tqdm progress bar
  --yaml YAML           Path to the YAML metadata file (for standalone
                        reassembly)
  --force               Overwrite output file if it exists
  --output OUTPUT       Path where the final target file will be saved
```

### Example Usage

The example below demonstrates downloading a
[Debian netinst ISO](https://cdimage.debian.org/debian-cd/current/amd64/iso-cd/) image 633MB with 32MB blocks
`https://cdimage.debian.org/debian-cd/current/amd64/iso-cd/debian-12.10.0-amd64-netinst.iso`

#### scripts/debian12
```bash
blockdownload \
  https://cdimage.debian.org/debian-cd/current/amd64/iso-cd/debian-12.10.0-amd64-netinst.iso \
  /tmp/debian12 \
  --name debian12 \
  --blocksize 32 \
  --unit MB \
  --boost 1 \
  --progress \
  --output /tmp/debian12/debian12.iso
```

#### How It Works

1. **Chunking**: The target file is split into blocks (32MB in the example)
2. **Parallel Download**: Each block is downloaded as a separate `.part` file
3. **Progress Tracking**: Real-time progress is displayed during download
4. **Assembly**: After downloading, blocks are reassembled into the final file
5. **Verification**: MD5 checksums verify the integrity of the final file

#### Output Files

The tool creates several files in the output directory:

- **Block files**: `{name}-{block_number}.part` - Each downloaded block
- **YAML metadata**: `{name}.yaml` - Contains block information, checksums, and offsets
- **Final file**: The reassembled target file
- **MD5 checksum**: `{name}.md5` - Verification of the final file

#### Parameters

| Parameter | Description |
|-----------|-------------|
| `--name` | Base name for download files |
| `--blocksize` | Size of each block |
| `--unit` | Unit for blocksize (KB, MB, GB) |
| `--boost` | Factor to improve download speed |
| `--progress` | Show download progress |
| `--output` | Path for the final assembled file |

#### Example Output

```
Creating target: 100%|███████████████████████| 664M/664M [00:00<00:00, 1.45GB/s]
created /tmp/debian12/debian12.iso - 633.00 MB
File reassembled successfully: /tmp/debian12/debian12.iso
Creating target: 100%|███████████████████████| 664M/664M [00:00<00:00, 1.43GB/s]
6b6604d894b6d861e357be1447b370db  /tmp/debian12/debian12.iso
```

#### Metadata Structure

The tool maintains a YAML file with detailed information about each block:

- Block number
- File path
- Offset position
- MD5 checksums (both for the entire block and block header)

This metadata allows for robust resumption of interrupted downloads and verification of data integrity.

```yaml
name: debian12
url: https://cdimage.debian.org/debian-cd/current/amd64/iso-cd/debian-12.10.0-amd64-netinst.iso
blocksize: 32
size: 663748608
unit: MB
chunk_size: 8192
md5: 6b6604d894b6d861e357be1447b370db
blocks:
- block: 0
  path: debian12-0000.part
  offset: 0
  md5: b94ec0df4842a004dee7eea04eb91119
  md5_head: c1708f385846feeb96eea7646e1cc14d
- block: 1
  path: debian12-0001.part
  offset: 33554432
  md5: f51efe8ee2ccf11745f2e0814afac48e
  md5_head: e4e89d6ece01b898440ef7c5ec03938c
- block: 2
  path: debian12-0002.part
  offset: 67108864
  md5: 4628498be89b83486c7a9ac34feb5662
  md5_head: 8c18d6a5313f84920599ab8869e99ad4
- block: 3
  path: debian12-0003.part
  offset: 100663296
  md5: 9ac5ade845864965088f11425da79733
  md5_head: 7200bfb69f3d8855ce36a08b40241ace
- block: 4
  path: debian12-0004.part
  offset: 134217728
  md5: 651d1afdeb96bfbdb2f0d1ff4eb7dc9f
  md5_head: 67836f61ac788d996931ec50d8cfe702
- block: 5
  path: debian12-0005.part
  offset: 167772160
  md5: b0a5944367270d4d0f460439e0515970
  md5_head: b781097a91c20a1c5c275c814b54e153
- block: 6
  path: debian12-0006.part
  offset: 201326592
  md5: 8609b0ab9534397f60d45953a51e1a7f
  md5_head: 2784576959977c5d6af30c9644704e6e
- block: 7
  path: debian12-0007.part
  offset: 234881024
  md5: e9de5729504f0275e546937630f158a8
  md5_head: 4a372b296c1dae51661a72e36c120e5c
- block: 8
  path: debian12-0008.part
  offset: 268435456
  md5: be8f6cdea534cb690aa061394ad6f77c
  md5_head: 770786dc612d1c319b1b3c9b2da44011
- block: 9
  path: debian12-0009.part
  offset: 301989888
  md5: 357ff7e961026d0722674ccf8e8cedc1
  md5_head: fbcdc0f7c0c4d6ef061bae4780d6d026
- block: 10
  path: debian12-0010.part
  offset: 335544320
  md5: 3e5a63a397ac81fe862848833ff6fde0
  md5_head: 85b1e258da5d1db4852def86a4664b8f
- block: 11
  path: debian12-0011.part
  offset: 369098752
  md5: a3cf4ee62f28dde9e1997f1166d2915d
  md5_head: 7e1f35e49cb45836614befb30e9a4ad5
- block: 12
  path: debian12-0012.part
  offset: 402653184
  md5: 2a6877a426d2a4a9b00e0416087d5920
  md5_head: fc081369872dfab4c7391d9d9c62491c
- block: 13
  path: debian12-0013.part
  offset: 436207616
  md5: 9bfd396bb5c7492174e233c23df17516
  md5_head: 8e0338b0d2ccba220da4cdc5f6811d6d
- block: 14
  path: debian12-0014.part
  offset: 469762048
  md5: 97774ebf805893e6fffc1d783b15e350
  md5_head: 3cc273002414d80e342afaafd94f8fc8
- block: 15
  path: debian12-0015.part
  offset: 503316480
  md5: 46c66aa5751a9c195073c5c42e6da7b5
  md5_head: b9f1d528ac7ce3c862e64ca055e23faf
- block: 16
  path: debian12-0016.part
  offset: 536870912
  md5: 271308910a719094c68ab605e134f1b7
  md5_head: 4c70a88e4e53ec232347b12670ca29d4
- block: 17
  path: debian12-0017.part
  offset: 570425344
  md5: 4a5813a5aa4c9f6aab172606283fa6af
  md5_head: f28a14c700238cf056c0f054f56de40d
- block: 18
  path: debian12-0018.part
  offset: 603979776
  md5: 53b21c20c2b9f85fd6ab14b6d8b50650
  md5_head: 25112155d35d8568338c99ba318b92a1
- block: 19
  path: debian12-0019.part
  offset: 637534208
  md5: 88c0e81466d1538b869fd5b8c3449a97
  md5_head: 97b251252405b0ee3e6d04e0499b2c1e
```


## Installation

You can install blockdownload using pip:

```bash
# Standard installation
pip install blockdownload

# Alternative if your default pip is not for Python 3
pip3 install blockdownload

# Local installation from source directory
pip install .
```

### Upgrading

To upgrade to the latest version:

```bash
# Standard upgrade
pip install blockdownload -U

# Alternative if your default pip is not for Python 3
pip3 install blockdownload -U
```

### Use Cases

- Downloading large ISO images
- Handling unstable internet connections
- Improving download speeds through parallelization
- Verifying integrity of large downloads

### Authors
* [Wolfgang Fahl](http://www.bitplan.com/Wolfgang_Fahl)