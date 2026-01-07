#!/usr/bin/env python3
"""
python3 zzz.py -s battle.py -c 3 -n mama -m 10 -r 4
Batch Submit Script for Apex Subnet 1
======================================
여러 miner hotkey로 동시에 솔루션을 제출하는 자동화 스크립트

사용법:
    python batch_submit.py --solution solution.py --competition-id 1
    python batch_submit.py --solution solution.py --competition-id 1 --wallet-dir /custom/path
    python batch_submit.py --solution solution.py --competition-id 1 --wallet-name butterfly --max-workers 10
    python batch_submit.py --solution solution.py --competition-id 1 --repeat 3 --repeat-delay 2.0
"""

import asyncio
import json
import time
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional
import httpx
from bittensor_wallet import Keypair
from hashlib import sha256
import uuid
from math import ceil

# ANSI colors for console output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"


class BatchSubmitter:
    def __init__(
        self,
        wallet_dir: str = None,
        orchestrator_url: str = None,
        spec_version: int = 100000,
        timeout: float = 60.0
    ):
        """
        Args:
            wallet_dir: Path to .bittensor/wallets directory
            orchestrator_url: Orchestrator API URL
            spec_version: Bittensor spec version
            timeout: HTTP request timeout
        """
        self.wallet_dir = Path(wallet_dir or Path.home() / ".bittensor" / "wallets")
        self.spec_version = spec_version
        self.timeout = timeout
        
        # Determine orchestrator URL (mainnet by default)
        if orchestrator_url:
            self.orchestrator_url = orchestrator_url
        else:
            self.orchestrator_url = "https://apex.api.macrocosmos.ai"
        
        print(f"{CYAN}[CONFIG]{RESET} Wallet directory: {self.wallet_dir}")
        print(f"{CYAN}[CONFIG]{RESET} Orchestrator URL: {self.orchestrator_url}")
        print(f"{CYAN}[CONFIG]{RESET} Timeout: {self.timeout}s")
        print()

    def find_all_hotkeys(self, wallet_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        지갑 디렉토리에서 모든 hotkey 파일을 찾습니다.
        
        Args:
            wallet_name: 특정 wallet만 스캔 (None이면 모든 wallet 스캔)
            
        Returns:
            List of dicts with: wallet_name, hotkey_name, hotkey_path, ss58_address
        """
        hotkeys = []
        
        if not self.wallet_dir.exists():
            print(f"{RED}[ERROR]{RESET} Wallet directory not found: {self.wallet_dir}")
            return hotkeys
        
        # Scan wallets
        wallet_dirs = [self.wallet_dir / wallet_name] if wallet_name else list(self.wallet_dir.iterdir())
        
        for wallet_path in wallet_dirs:
            if not wallet_path.is_dir():
                continue
            
            wallet_name = wallet_path.name
            hotkeys_dir = wallet_path / "hotkeys"
            
            if not hotkeys_dir.exists():
                continue
            
            # Scan hotkeys in this wallet
            for hotkey_file in hotkeys_dir.iterdir():
                if not hotkey_file.is_file():
                    continue
                
                # Skip pub.txt files (they're just public key copies)
                if hotkey_file.name.endswith('.txt') or hotkey_file.name.endswith('pub'):
                    continue
                
                try:
                    with open(hotkey_file, "r") as f:
                        key_data = json.load(f)
                    
                    ss58_address = key_data.get("ss58Address")
                    if not ss58_address:
                        continue
                    
                    hotkeys.append({
                        "wallet_name": wallet_name,
                        "hotkey_name": hotkey_file.name,
                        "hotkey_path": str(hotkey_file),
                        "ss58_address": ss58_address,
                    })
                    
                except Exception as e:
                    print(f"{YELLOW}[WARN]{RESET} Failed to read {hotkey_file}: {e}")
                    continue
        
        return hotkeys

    def load_keypair(self, hotkey_path: str) -> Keypair:
        """Load Keypair from hotkey file"""
        with open(hotkey_path, "r") as f:
            key_data = json.load(f)
        
        private_key = key_data.get("privateKey")
        if not private_key:
            raise ValueError("No private key found in key file")
        
        # Remove 0x prefix if present
        if private_key.startswith("0x"):
            private_key = private_key[2:]
        
        private_key_bytes = bytes.fromhex(private_key)
        private_key = private_key_bytes.hex()
        
        return Keypair.create_from_private_key(private_key)

    def create_message_body(self, data: dict) -> bytes:
        """Create message body for signing"""
        return json.dumps(data, default=str, sort_keys=True).encode("utf-8")

    def generate_header(self, hotkey: Keypair, body: bytes) -> dict[str, Any]:
        """Generate Epistula authentication headers"""
        timestamp = round(time.time() * 1000)
        message = f"{sha256(body).hexdigest()}.{timestamp}."
        
        headers = {
            "Epistula-Timestamp": str(timestamp),
            "Epistula-Signed-By": hotkey.ss58_address,
            "Epistula-Request-Signature": "0x" + hotkey.sign(message).hex(),
            "X-Spec-Version": str(self.spec_version),
            "X-Request-Id": str(uuid.uuid4()),
            "Content-Type": "application/json",
        }
        
        return headers

    async def submit_single(
        self,
        hotkey_info: Dict[str, Any],
        code: str,
        competition_id: int,
        round_number: int = -1
    ) -> Dict[str, Any]:
        """
        단일 hotkey로 솔루션 제출
        
        Returns:
            Dict with: success, hotkey, wallet_name, response, error
        """
        hotkey_path = hotkey_info["hotkey_path"]
        ss58_address = hotkey_info["ss58_address"]
        wallet_name = hotkey_info["wallet_name"]
        hotkey_name = hotkey_info["hotkey_name"]
        
        result = {
            "success": False,
            "hotkey": ss58_address,
            "hotkey_short": ss58_address[:8],
            "wallet_name": wallet_name,
            "hotkey_name": hotkey_name,
            "response": None,
            "error": None,
            "duration": 0,
        }
        
        start_time = time.time()
        
        try:
            # Load keypair
            keypair = self.load_keypair(hotkey_path)
            
            # Create submission request
            submit_request = {
                "competition_id": competition_id,
                "round_number": round_number,
                "raw_code": code,
            }
            
            # Create signed headers
            body_bytes = self.create_message_body(submit_request)
            headers = self.generate_header(keypair, body_bytes)
            
            # Make HTTP request
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.orchestrator_url}/miner/submission",
                    json=submit_request,
                    headers=headers,
                )
                
                result["duration"] = time.time() - start_time
                
                if response.status_code == 200:
                    result["success"] = True
                    result["response"] = response.json()
                else:
                    result["error"] = f"HTTP {response.status_code}: {response.text}"
                    
        except Exception as e:
            result["duration"] = time.time() - start_time
            result["error"] = str(e)
        
        return result

    async def batch_submit(
        self,
        hotkeys: List[Dict[str, Any]],
        code: str,
        competition_id: int,
        max_workers: int = 5,
        delay_between_batches: float = 0.0,
        repeat: int = 1,
        delay_between_repeats: float = 0.0
    ) -> List[Dict[str, Any]]:
        """
        여러 hotkey로 병렬 제출
        
        Args:
            hotkeys: List of hotkey info dicts
            code: Solution code
            competition_id: Competition ID
            max_workers: Maximum parallel submissions
            delay_between_batches: Delay between batches (seconds)
            repeat: Number of times to repeat submission (default: 1)
            delay_between_repeats: Delay between repeats (seconds)
            
        Returns:
            List of submission results
        """
        print(f"{BOLD}{BLUE}[BATCH SUBMIT]{RESET} Starting submission for {len(hotkeys)} hotkeys")
        print(f"{BLUE}[BATCH SUBMIT]{RESET} Max workers: {max_workers}")
        print(f"{BLUE}[BATCH SUBMIT]{RESET} Competition ID: {competition_id}")
        print(f"{BLUE}[BATCH SUBMIT]{RESET} Repeat count: {repeat}")
        print()
        
        all_results = []
        
        # Repeat submission
        for repeat_num in range(1, repeat + 1):
            if repeat > 1:
                print(f"{BOLD}{YELLOW}[REPEAT {repeat_num}/{repeat}]{RESET}")
                print()
            
            results = []
            
            # Process in batches
            for i in range(0, len(hotkeys), max_workers):
                batch = hotkeys[i:i + max_workers]
                batch_num = i // max_workers + 1
                total_batches = (len(hotkeys) + max_workers - 1) // max_workers
                
                print(f"{CYAN}[BATCH {batch_num}/{total_batches}]{RESET} Submitting {len(batch)} hotkeys...")
                
                # Create tasks for this batch
                tasks = [
                    self.submit_single(hotkey_info, code, competition_id)
                    for hotkey_info in batch
                ]
                
                # Execute batch concurrently
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Process results
                for idx, result in enumerate(batch_results):
                    if isinstance(result, Exception):
                        result = {
                            "success": False,
                            "hotkey": batch[idx]["ss58_address"],
                            "error": str(result),
                        }
                    
                    # Add repeat number to result
                    result["repeat_num"] = repeat_num
                    results.append(result)
                    
                    # Print individual result
                    if result["success"]:
                        print(f"  {GREEN}✓{RESET} {result['hotkey_short']} | "
                              f"{result['wallet_name']}/{result['hotkey_name']} | "
                              f"{result['duration']:.2f}s")
                    else:
                        print(f"  {RED}✗{RESET} {result['hotkey_short']} | "
                              f"{result['wallet_name']}/{result['hotkey_name']} | "
                              f"{result['error']}")
                
                # Delay between batches
                if i + max_workers < len(hotkeys) and delay_between_batches > 0:
                    print(f"{YELLOW}[WAIT]{RESET} Waiting {delay_between_batches}s before next batch...")
                    await asyncio.sleep(delay_between_batches)
                
                print()
            
            all_results.extend(results)
            
            # Delay between repeats
            if repeat_num < repeat and delay_between_repeats > 0:
                print(f"{YELLOW}[WAIT]{RESET} Waiting {delay_between_repeats}s before next repeat...")
                await asyncio.sleep(delay_between_repeats)
                print()
        
        return all_results

    def print_summary(self, results: List[Dict[str, Any]]):
        """Print submission summary"""
        total = len(results)
        successful = sum(1 for r in results if r["success"])
        failed = total - successful
        
        print(f"{BOLD}{'=' * 70}{RESET}")
        print(f"{BOLD}{CYAN}SUBMISSION SUMMARY{RESET}")
        print(f"{BOLD}{'=' * 70}{RESET}")
        print(f"Total submissions: {total}")
        print(f"{GREEN}Successful: {successful}{RESET}")
        print(f"{RED}Failed: {failed}{RESET}")
        
        # Check if we have repeat information
        repeats = set(r.get("repeat_num") for r in results if "repeat_num" in r)
        if len(repeats) > 1:
            print(f"Number of repeats: {max(repeats)}")
            for repeat_num in sorted(repeats):
                repeat_results = [r for r in results if r.get("repeat_num") == repeat_num]
                repeat_success = sum(1 for r in repeat_results if r["success"])
                print(f"  Repeat {repeat_num}: {repeat_success}/{len(repeat_results)} successful")
        
        if successful > 0:
            avg_duration = sum(r["duration"] for r in results if r["success"]) / successful
            print(f"Average duration: {avg_duration:.2f}s")
        
        print(f"{BOLD}{'=' * 70}{RESET}")
        
        # Print failed submissions details
        if failed > 0:
            print(f"\n{RED}{BOLD}Failed Submissions:{RESET}")
            for result in results:
                if not result["success"]:
                    repeat_info = f" [Repeat {result['repeat_num']}]" if "repeat_num" in result else ""
                    print(f"  {RED}✗{RESET} {result.get('hotkey_short', 'unknown')}{repeat_info}: {result.get('error', 'Unknown error')}")


def main():
    parser = argparse.ArgumentParser(
        description="Batch submit solution to multiple miner hotkeys",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Submit to all hotkeys in default wallet directory
  python batch_submit.py --solution solution.py --competition-id 1
  
  # Submit to specific wallet only
  python batch_submit.py --solution solution.py --competition-id 1 --wallet-name butterfly
  
  # Custom wallet directory and max workers
  python batch_submit.py --solution solution.py --competition-id 1 --wallet-dir /custom/path --max-workers 10
  
  # With delay between batches
  python batch_submit.py --solution solution.py --competition-id 1 --max-workers 5 --delay 1.0
  
  # Repeat submission 3 times for each hotkey
  python batch_submit.py --solution solution.py --competition-id 1 --repeat 3
  
  # Repeat 5 times with 2 second delay between repeats
  python batch_submit.py --solution solution.py --competition-id 1 --repeat 5 --repeat-delay 2.0
        """
    )
    
    parser.add_argument(
        "--solution", "-s",
        required=True,
        help="Path to solution file (Python code)"
    )
    
    parser.add_argument(
        "--competition-id", "-c",
        type=int,
        required=True,
        help="Competition ID"
    )
    
    parser.add_argument(
        "--wallet-dir", "-w",
        default=None,
        help="Path to wallet directory (default: ~/.bittensor/wallets)"
    )
    
    parser.add_argument(
        "--wallet-name", "-n",
        default=None,
        help="Specific wallet name (default: scan all wallets)"
    )
    
    parser.add_argument(
        "--max-workers", "-m",
        type=int,
        default=5,
        help="Maximum parallel submissions (default: 5)"
    )
    
    parser.add_argument(
        "--delay", "-d",
        type=float,
        default=0.0,
        help="Delay between batches in seconds (default: 0)"
    )
    
    parser.add_argument(
        "--repeat", "-r",
        type=int,
        default=1,
        help="Number of times to repeat submission for each hotkey (default: 1)"
    )
    
    parser.add_argument(
        "--repeat-delay",
        type=float,
        default=0.0,
        help="Delay between repeats in seconds (default: 0)"
    )
    
    parser.add_argument(
        "--orchestrator-url", "-o",
        default=None,
        help="Orchestrator URL (default: https://apex.api.macrocosmos.ai)"
    )
    
    parser.add_argument(
        "--timeout", "-t",
        type=float,
        default=60.0,
        help="HTTP request timeout in seconds (default: 60)"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List hotkeys without submitting"
    )
    
    args = parser.parse_args()
    
    # Read solution code
    solution_path = Path(args.solution)
    if not solution_path.exists():
        print(f"{RED}[ERROR]{RESET} Solution file not found: {solution_path}")
        return 1
    
    try:
        with open(solution_path, "r", encoding="utf-8") as f:
            code = f.read().strip()
    except Exception as e:
        print(f"{RED}[ERROR]{RESET} Failed to read solution file: {e}")
        return 1
    
    if not code:
        print(f"{RED}[ERROR]{RESET} Solution file is empty")
        return 1
    
    print(f"{GREEN}[OK]{RESET} Solution loaded: {len(code)} characters")
    print()
    
    # Initialize submitter
    submitter = BatchSubmitter(
        wallet_dir=args.wallet_dir,
        orchestrator_url=args.orchestrator_url,
        timeout=args.timeout
    )
    
    # Find all hotkeys
    print(f"{BLUE}[SCAN]{RESET} Scanning for hotkeys...")
    hotkeys = submitter.find_all_hotkeys(wallet_name=args.wallet_name)
    
    if not hotkeys:
        print(f"{RED}[ERROR]{RESET} No hotkeys found!")
        return 1
    
    print(f"{GREEN}[OK]{RESET} Found {len(hotkeys)} hotkeys:")
    for hk in hotkeys:
        print(f"  • {hk['wallet_name']}/{hk['hotkey_name']} [{hk['ss58_address'][:8]}...]")
    print()
    
    # Dry run mode
    if args.dry_run:
        print(f"{YELLOW}[DRY RUN]{RESET} Exiting without submission")
        return 0
    
    # Auto-submit without confirmation
    total_submissions = len(hotkeys) * args.repeat
    print(f"{GREEN}[AUTO-SUBMIT]{RESET} Starting submission for {len(hotkeys)} hotkeys × {args.repeat} repeat(s) = {total_submissions} total submissions")
    print(f"{GREEN}[AUTO-SUBMIT]{RESET} Competition ID: {args.competition_id}")
    print()
    
    # Batch submit
    start_time = time.time()
    results = asyncio.run(submitter.batch_submit(
        hotkeys=hotkeys,
        code=code,
        competition_id=args.competition_id,
        max_workers=args.max_workers,
        delay_between_batches=args.delay,
        repeat=args.repeat,
        delay_between_repeats=args.repeat_delay
    ))
    total_time = time.time() - start_time
    
    # Print summary
    submitter.print_summary(results)
    print(f"\nTotal execution time: {total_time:.2f}s")
    
    # Return exit code
    return 0 if all(r["success"] for r in results) else 1


if __name__ == "__main__":
    exit(main())

