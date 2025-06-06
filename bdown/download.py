"""
Created on 2025-05-05

@author: wf
"""
from concurrent.futures import ThreadPoolExecutor
import glob
import os
from queue import Queue
import subprocess
from threading import Lock
from typing import List

from bdown.block import Block, StatusSymbol, BlockIterator
from bdown.block_fiddler import BlockFiddler
from lodstorage.yamlable import lod_storable
import requests

@lod_storable
class BlockDownload(BlockFiddler):
    url: str = None

    def __post_init__(self):
        """
        specialized @constructor time initialization
        """
        # call the general  @constructor time initialization
        super().__post_init__()
        self.active_blocks = set()
        self.progress_lock = Lock()
        # Add a queue for thread-safe block collection
        self.block_queue = Queue()
        if self.size is None:
            self.size = self.get_remote_file_size()

    def download_via_os(self, target_path: str, cmd=None) -> int:
        """
        Download file using operating system command

        Args:
            target_path: Path where the file should be saved
            cmd: Command to execute as list, defaults to wget

        Returns:
            int: Size of the downloaded file in bytes, or -1 if download failed

        Raises:
            subprocess.CalledProcessError: If the command returns a non-zero exit code
        """
        if cmd is None:
            cmd = ["wget", "--quiet", "-O", target_path, self.url]
        subprocess.run(cmd, check=True)

        if os.path.exists(target_path):
            return os.path.getsize(target_path)
        return -1

    def block_range_str(self) -> str:
        if not self.active_blocks:
            range_str = "∅"
        else:
            min_block = min(self.active_blocks)
            max_block = max(self.active_blocks)
            range_str = (
                f"{min_block:04d}-{min_block:04d}" if min_block == max_block else f"{min_block:04d}–{max_block:04d}"
            )
        return range_str

    @classmethod
    def ofYamlPath(cls, yaml_path: str):
        block_download = cls.load_from_yaml_file(yaml_path)
        block_download.yaml_path = yaml_path
        block_download.check_blocks_from_part_yaml_files()
        block_download.set_blocks_state()
        return block_download

    def set_blocks_state(self):
        # Determine final state
        no_issues = len(self.issues) == 0
        all_blocks_present = len(self.blocks) == self.total_blocks

        if all_blocks_present and no_issues:
            self.blocks_state = "complete_consistent"
        elif len(self.blocks) == 0:
            self.blocks_state = "stub_empty"
        else:
            self.self.blocks_state= "incomplete_inconsistent"

    def check_blocks_from_part_yaml_files(self):
        """
        Check consistency between main YAML blocks and part YAML files

        There are three cases:
           no blocks yet - we will retrieve all from the part YAML files
           a complete and consistent list of blocks - this is the state we should
           have after reassembly allowing to remove all part files and yaml files since
           a filesplit can easily recreate locally
           an incomplete/inconsistent list of blocks - patching might be viable but reassembly
           is not possible yet
        """
        def add_issue(issues, block_index: int, issue: str):
            if block_index not in issues:
                issues[block_index] = []
            issues[block_index].append(issue)

        yaml_dir = os.path.dirname(self.yaml_path)
        self.blocks_by_index = {}
        self.issues = {}

        # Index existing blocks
        for block in self.blocks:
            block_exists = block.block in self.blocks_by_index
            if block_exists:
                add_issue(self.issues, block.block, "duplicate")
            else:
                self.blocks_by_index[block.block] = block

        # Check part files
        for bi in range(self.total_blocks):
            block_yaml = os.path.join(yaml_dir, f"{self.name}-{bi:04d}.yaml")
            part_file_exists = os.path.exists(block_yaml)

            if part_file_exists:
                part_block = Block.load_from_yaml_file(block_yaml) # @UndefinedVariable
                main_block_exists = bi in self.blocks_by_index

                if not main_block_exists:
                    # No main block - add from part file
                    self.blocks.append(part_block)
                    self.blocks_by_index[bi] = part_block
                else:
                    # Check consistency
                    main_block = self.blocks_by_index[bi]
                    is_consistent = main_block.is_consistent(part_block)
                    if not is_consistent:
                        add_issue(self.issues, bi, "inconsistent")

    def get_remote_file_size(self) -> int:
        response = requests.head(self.url, allow_redirects=True)
        response.raise_for_status()
        file_size = int(response.headers.get("Content-Length", 0))
        return file_size

    def boosted_download(self, block_specs, target, progress_bar, boost, force):
        """Handle parallel downloading of blocks with proper tracking"""
        processed_blocks = set()
        with ThreadPoolExecutor(max_workers=boost) as executor:
            futures = []
            for index, start, end in block_specs:
                future = executor.submit(
                    self.download_block, index, start, end, target, progress_bar,force
                )
                futures.append((index, future))

            # Wait for all tasks to complete and track which completed successfully
            for index, future in futures:
                try:
                    future.result()
                    processed_blocks.add(index)
                except Exception as e:
                    print(f"Error processing block {index}: {e}")

        return processed_blocks

    def download(
        self,
        target: str,
        from_block: int = 0,
        to_block: int = None,
        boost: int = 1,
        progress_bar=None,
        force: bool=False
    ):
        """
        Download selected blocks and save them to individual .part files.

        Args:
            target: Directory to store .part files.
            from_block: Index of the first block to download.
            to_block: Index of the last block (inclusive), or None to download until end.
            boost: Number of parallel download threads to use (default: 1 = serial).
            progress_bar: Optional tqdm-compatible progress bar for visual feedback.
            force: if True override existing files unconditionally
        """
        if self.size is None:
            self.size = self.get_remote_file_size()
        os.makedirs(target, exist_ok=True)

        if to_block is None:
            total_blocks = (
                self.size + self.blocksize_bytes - 1
            ) // self.blocksize_bytes
            to_block = total_blocks - 1

        block_specs = self.block_ranges(from_block, to_block)
        # Save YAML early for otf synchronization
        self.save()

        if boost == 1:
            for index, start, end in block_specs:
                self.download_block(index, start, end, target, progress_bar,force)
        else:
            boosted_blocks=self.boosted_download(block_specs, target, progress_bar, boost,force)
            # Check if we processed all expected blocks
            expected_blocks = set(range(from_block, to_block + 1))
            missed_blocks = expected_blocks - boosted_blocks
            if missed_blocks:
                print(f"{StatusSymbol.WARN}: Failed to process blocks: {sorted(missed_blocks)}")

        # After all downloads are complete, collect and save the blocks
        self.save_blocks(target)

    def update_progress(self, progress_bar, index: int):
        """
        Update the progress bar based on block activity.

        Args:
            progress_bar: tqdm progress bar instance (optional)
            index (int):
                - positive → block started (add to active)
                - negative → block finished (remove from active)
        """
        with self.progress_lock:
            if index > 0:
                self.active_blocks.add(index)
            else:
                self.active_blocks.discard(-index)
            if progress_bar:
                msg=f"{self.name} {self.block_range_str()}"
                progress_bar.set_description(msg)

    def download_block(
        self,
        index: int,
        start: int,
        end: int,
        target: str,
        progress_bar,
        force: bool = False
    ):
        """
        Download a single block of data from the URL to a part file.

        Args:
            index: Block index number
            start: Starting byte offset for the range request
            end: Ending byte offset for the range request
            target: Target directory to save the part file
            progress_bar: Progress bar to update during download
            force: bool: if true override existing files unconditionally

        Side effects:
            - Creates .part file with downloaded data
            - Creates .yaml file with block metadata
            - Updates progress bar
            - Adds block to thread-safe queue
        """
        part_name = f"{self.name}-{index:04d}"
        part_file = os.path.join(target, f"{part_name}.part")
        block_yaml_path = os.path.join(target, f"{part_name}.yaml")
        block_size = end - start + 1

        # Check existing block using Block methods
        has_existing_block = index < len(self.blocks)
        if has_existing_block:
            existing_block = self.blocks[index]
            existing_block.path = part_name + ".part"  # Set relative path for validation

            block_is_valid = existing_block.is_valid(target, check_head=True)
            if block_is_valid and not force:
                msg=f"✅ {part_name} already valid, skipping"
                self.logger.info(msg)
                if progress_bar:
                    progress_bar.set_description(part_name)
                    progress_bar.update(block_size)
                existing_block.ensure_yaml(target)
                return
        else:
            # No existing metadata, check if file exists
            file_present = os.path.exists(part_file)
            if file_present and not force:
                msg=f"⚠️ ️{part_name}.part file exists, use --force to overwrite"
                self.logger.warning(msg)
                return

        # Download new block
        self.logger.info(f"Downloading block {index}: bytes {start}-{end}")
        self.update_progress(progress_bar, index + 1)

        headers = {"Range": f"bytes={start}-{end}"}
        response = requests.get(self.url, headers=headers, stream=True)

        response_valid = response.status_code in (200, 206)
        if not response_valid:
            error_message = f"HTTP {response.status_code}: {response.text}"
            self.logger.error(error_message)
            raise Exception(error_message)

        block_path = os.path.basename(part_file)

        with open(part_file, "wb") as target_file:
            bi = BlockIterator(
                index=index,
                offset=start,
                size=block_size,
                block_path=block_path,
                progress_bar=progress_bar,
                target_file=target_file,
                chunk_size=self.chunk_size,
                # do not try to calculate total hashes
                hash_total=self.total_hash
            )

            downloaded_block = Block.ofResponse(bi, response)
            downloaded_block.save_to_yaml_file(block_yaml_path)
            self.block_queue.put(downloaded_block)

        self.logger.info(f"✅ {part_name} downloaded successfully")
        self.update_progress(progress_bar, -(index + 1))

    def save_blocks(self, target_dir):
        """Save blocks and verify against the separately collected blocks"""
        while not self.block_queue.empty():
            self.blocks.append(self.block_queue.get())

        # First sort and save all blocks
        self.save()

        # Now check that the collected blocks are the same as what we've downloaded
        cblocks = self.collect_blocks(target_dir)

        # Sort both sets of blocks for comparison
        cblocks.sort(key=lambda b: b.offset)
        self.sort_blocks()

        # Compare block counts
        if len(cblocks) != len(self.blocks):
            print(f"⚠️  Collected {len(cblocks)} blocks but have {len(self.blocks)} in memory")


    def collect_blocks(self,target_dir)->List[Block]:
        """Collect all block YAMLs"""
        block_files = glob.glob(os.path.join(target_dir, f"{self.name}-*.yaml"))
        blocks=[]
        for block_file in sorted(block_files):
            block = Block.load_from_yaml_file(block_file) # @UndefinedVariable
            blocks.append(block)
        return blocks
