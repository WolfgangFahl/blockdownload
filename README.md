# blockdownload
download large files with parallel blocks


[![pypi](https://img.shields.io/pypi/pyversions/blockdownload)](https://pypi.org/project/blockdownload/)
[![Github Actions Build](https://github.com/WolfgangFahl/blockdownload/actions/workflows/build.yml/badge.svg)](https://github.com/WolfgangFahl/blockdownload/actions/workflows/build.yml)
[![PyPI Status](https://img.shields.io/pypi/v/blockdownload.svg)](https://pypi.python.org/pypi/blockdownload/)
[![GitHub issues](https://img.shields.io/github/issues/WolfgangFahl/blockdownload.svg)](https://github.com/WolfgangFahl/blockdownload/issues)
[![GitHub closed issues](https://img.shields.io/github/issues-closed/WolfgangFahl/blockdownload.svg)](https://github.com/WolfgangFahl/blockdownload/issues/?q=is%3Aissue+is%3Aclosed)
[![API Docs](https://img.shields.io/badge/API-Documentation-blue)](https://WolfgangFahl.github.io/blockdownload/)
[![License](https://img.shields.io/github/license/WolfgangFahl/blockdownload.svg)](https://www.apache.org/licenses/LICENSE-2.0)

## Documentation
[Wiki](http://wiki.bitplan.com/index.php/blockdownload)

## Usage
```bash
blockdownload -h
usage: blockdownload [-h] --name NAME [--blocksize BLOCKSIZE] [--unit {KB,MB,GB}]
                     [--from-block FROM_BLOCK] [--to-block TO_BLOCK]
                     [--boost BOOST] [--progress]
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
```

### Authors
* [Wolfgang Fahl](http://www.bitplan.com/Wolfgang_Fahl)