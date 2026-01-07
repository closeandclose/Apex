#!/usr/bin/env python3
"""
Command Bot - Executes terminal commands with automatic retry on errors.
Supports hotkey rotation and command repetition.
"""

import subprocess
import sys
import time
import argparse
from typing import Optional, List
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

console = Console()

# ============================================================================
# CONFIGURATION - Edit these values to customize behavior
# ============================================================================

# Wallet name to use for linking
WALLET_NAME = "mama"

# List of hotkeys to cycle through
HOTKEY_LIST = [
    # battle competition
    "apex0", "apex1", "apex2", "apex3", "apex4", "apex5", "apex6", "apex7", "apex8", "apex9", 
    "apex10", "apex11", "apex12", "apex13", "apex14", "apex15", "apex16", "apex17", "apex18", "apex19", 
    "apex20", "apex21", "apex22", "apex23", "apex24", "apex25", "apex26", "apex27", "apex28", "apex29", 
    "apex80", "apex81", "apex82", "apex83", "apex84", "apex85", "apex86", "apex87", "apex88", "apex89",
    "apex90", "apex91", "apex92", "apex93", "apex94", "apex95", "apex96", "apex97", "apex98",


]

# Command to run after linking each hotkey
COMMAND_TO_RUN = "apex submit apexmatrix.py -c 1"

# Number of times to repeat the command for each hotkey
REPETITIONS_PER_HOTKEY = 2

# ============================================================================
# End of configuration
# ============================================================================


class CommandBot:
    """Bot that executes commands with retry logic."""
    
    def __init__(
        self,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        show_output: bool = True,
        stop_on_success: bool = True,
    ):
        """
        Initialize the command bot.
        
        Args:
            max_retries: Maximum number of retry attempts (default: 3)
            retry_delay: Delay in seconds between retries (default: 1.0)
            show_output: Whether to show command output (default: True)
            stop_on_success: Stop retrying after first success (default: True)
        """
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.show_output = show_output
        self.stop_on_success = stop_on_success
        self.attempts = []
    
    def run_command(
        self,
        command: str | List[str],
        shell: bool = False,
        cwd: Optional[str] = None,
        env: Optional[dict] = None,
    ) -> tuple[int, str, str]:
        """
        Run a command with retry logic.
        
        Args:
            command: Command to execute (string or list)
            shell: Whether to use shell execution
            cwd: Working directory
            env: Environment variables
        
        Returns:
            Tuple of (exit_code, stdout, stderr)
        """
        cmd_str = command if isinstance(command, str) else " ".join(str(c) for c in command)
        
        console.print(f"\n[cyan]Executing:[/cyan] [bold]{cmd_str}[/bold]")
        
        for attempt in range(1, self.max_retries + 1):
            try:
                result = subprocess.run(
                    command,
                    shell=shell,
                    capture_output=True,
                    text=True,
                    cwd=cwd,
                    env=env,
                )
                
                success = result.returncode == 0
                self.attempts.append({
                    "attempt": attempt,
                    "command": cmd_str,
                    "exit_code": result.returncode,
                    "success": success,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                })
                
                if success:
                    console.print(f"[green]✓ Success on attempt {attempt}[/green]")
                    if self.show_output and result.stdout:
                        console.print(Panel(result.stdout, title="Output", border_style="green"))
                    if self.stop_on_success:
                        return result.returncode, result.stdout, result.stderr
                else:
                    console.print(f"[red]✗ Failed on attempt {attempt} (exit code: {result.returncode})[/red]")
                    if self.show_output:
                        if result.stdout:
                            console.print(Panel(result.stdout, title="Stdout", border_style="yellow"))
                        if result.stderr:
                            console.print(Panel(result.stderr, title="Stderr", border_style="red"))
                    
                    if attempt < self.max_retries:
                        console.print(f"[yellow]Retrying in {self.retry_delay} seconds...[/yellow]")
                        time.sleep(self.retry_delay)
                    else:
                        console.print(f"[red]Max retries ({self.max_retries}) reached. Giving up.[/red]")
                
            except Exception as e:
                console.print(f"[red]✗ Exception on attempt {attempt}: {e}[/red]")
                self.attempts.append({
                    "attempt": attempt,
                    "command": cmd_str,
                    "exit_code": -1,
                    "success": False,
                    "stdout": "",
                    "stderr": str(e),
                })
                
                if attempt < self.max_retries:
                    console.print(f"[yellow]Retrying in {self.retry_delay} seconds...[/yellow]")
                    time.sleep(self.retry_delay)
                else:
                    console.print(f"[red]Max retries ({self.max_retries}) reached. Giving up.[/red]")
                    return -1, "", str(e)
        
        # Return last attempt's result
        last_attempt = self.attempts[-1]
        return last_attempt["exit_code"], last_attempt["stdout"], last_attempt["stderr"]
    
    def run_commands(
        self,
        commands: List[str | List[str]],
        shell: bool = False,
        cwd: Optional[str] = None,
        stop_on_error: bool = False,
    ) -> List[tuple[int, str, str]]:
        """
        Run multiple commands sequentially.
        
        Args:
            commands: List of commands to execute
            shell: Whether to use shell execution (auto-detected for string commands)
            cwd: Working directory
            stop_on_error: Stop execution if a command fails
        
        Returns:
            List of (exit_code, stdout, stderr) tuples
        """
        results = []
        for i, cmd in enumerate(commands, 1):
            console.print(f"\n[bold blue]Command {i}/{len(commands)}[/bold blue]")
            # Auto-detect shell mode: use shell if command is a string
            use_shell = shell or isinstance(cmd, str)
            exit_code, stdout, stderr = self.run_command(cmd, shell=use_shell, cwd=cwd)
            results.append((exit_code, stdout, stderr))
            
            if stop_on_error and exit_code != 0:
                console.print(f"[red]Stopping execution due to error in command {i}[/red]")
                break
        
        return results
    
    def show_summary(self):
        """Show a summary of all attempts."""
        if not self.attempts:
            return
        
        table = Table(title="Execution Summary", box=box.ROUNDED)
        table.add_column("Attempt", style="cyan", no_wrap=True)
        table.add_column("Command", style="magenta")
        table.add_column("Exit Code", justify="right", style="yellow")
        table.add_column("Status", justify="center")
        
        for attempt in self.attempts:
            cmd_display = attempt["command"][:50] + "..." if len(attempt["command"]) > 50 else attempt["command"]
            status = "[green]✓ Success[/green]" if attempt["success"] else "[red]✗ Failed[/red]"
            table.add_row(
                str(attempt["attempt"]),
                cmd_display,
                str(attempt["exit_code"]),
                status,
            )
        
        console.print("\n")
        console.print(table)
        
        # Statistics
        total = len(self.attempts)
        successful = sum(a["success"] for a in self.attempts)
        failed = total - successful
        
        console.print(f"\n[bold]Statistics:[/bold]")
        console.print(f"  Total attempts: {total}")
        console.print(f"  [green]Successful: {successful}[/green]")
        console.print(f"  [red]Failed: {failed}[/red]")
    
    def run_with_hotkey_rotation(
        self,
        hotkeys: List[str],
        wallet: str,
        command: str,
        repetitions: int = 4,
        link_retries: int = 3,
    ) -> dict:
        """
        Cycle through hotkeys, link each one, and run a command multiple times.
        
        Args:
            hotkeys: List of hotkey names
            wallet: Wallet name to use
            command: Command to run after linking
            repetitions: Number of times to run command per hotkey
            link_retries: Number of retries for linking command
        
        Returns:
            Dictionary with results for each hotkey
        """
        results = {}
        
        console.print(Panel(
            f"[bold]Hotkey Rotation Mode[/bold]\n"
            f"Wallet: {wallet}\n"
            f"Hotkeys: {len(hotkeys)}\n"
            f"Command: {command}\n"
            f"Repetitions per hotkey: {repetitions}",
            title="Configuration",
            border_style="cyan",
        ))
        
        for hotkey_idx, hotkey in enumerate(hotkeys, 1):
            console.print(f"\n[bold cyan]{'='*60}[/bold cyan]")
            console.print(f"[bold cyan]Hotkey {hotkey_idx}/{len(hotkeys)}: {hotkey}[/bold cyan]")
            console.print(f"[bold cyan]{'='*60}[/bold cyan]\n")
            
            # Link the hotkey
            link_command = f"apex link --wallet {wallet} --hotkey {hotkey}"
            console.print(f"[yellow]Linking hotkey: {hotkey}[/yellow]")
            
            link_exit_code, link_stdout, link_stderr = self.run_command(
                link_command,
                shell=True,
            )
            
            if link_exit_code != 0:
                console.print(f"[red]Failed to link hotkey {hotkey}. Skipping...[/red]")
                results[hotkey] = {
                    "linked": False,
                    "command_results": [],
                }
                continue
            
            console.print(f"[green]✓ Successfully linked hotkey: {hotkey}[/green]\n")
            
            # Run the command multiple times
            command_results = []
            for rep in range(1, repetitions + 1):
                console.print(f"\n[yellow]━━━ Running command {rep}/{repetitions} for hotkey {hotkey} ━━━[/yellow]")
                console.print(f"[dim]Command: {command}[/dim]")
                
                # Auto-confirm prompts by piping "yes" to the command
                auto_confirm_command = f'echo "yes" | {command}'
                
                exit_code, stdout, stderr = self.run_command(
                    auto_confirm_command,
                    shell=True,  # Always use shell mode for bash-like execution
                )
                command_results.append({
                    "repetition": rep,
                    "exit_code": exit_code,
                    "success": exit_code == 0,
                    "stdout": stdout,
                    "stderr": stderr,
                })
                
                if exit_code == 0:
                    console.print(f"[green]✓ Command {rep}/{repetitions} succeeded[/green]")
                else:
                    console.print(f"[red]✗ Command {rep}/{repetitions} failed (exit code: {exit_code})[/red]")
                    if stderr:
                        console.print(f"[red]Error: {stderr[:200]}[/red]")
                
                # Small delay between repetitions (except for the last one)
                if rep < repetitions:
                    time.sleep(0.5)
            
            results[hotkey] = {
                "linked": True,
                "command_results": command_results,
            }
            
            # Summary for this hotkey
            successful = sum(r["success"] for r in command_results)
            failed = repetitions - successful
            console.print(f"\n[bold]Hotkey {hotkey} Summary:[/bold]")
            console.print(f"  [green]Successful: {successful}/{repetitions}[/green]")
            console.print(f"  [red]Failed: {failed}/{repetitions}[/red]")
        
        return results


def show_hotkey_rotation_summary(results: dict, show_table: bool = True):
    """Display summary of hotkey rotation results."""
    console.print("\n" + "="*60)
    console.print("[bold cyan]Final Summary[/bold cyan]")
    console.print("="*60)
    
    total_hotkeys = len(results)
    linked_hotkeys = sum(1 for r in results.values() if r["linked"])
    total_commands = sum(len(r["command_results"]) for r in results.values())
    successful_commands = sum(
        sum(cr["success"] for cr in r["command_results"])
        for r in results.values()
    )
    failed_commands = total_commands - successful_commands
    
    console.print(f"\n[bold]Overall Statistics:[/bold]")
    console.print(f"  Hotkeys processed: {total_hotkeys}")
    console.print(f"  [green]Successfully linked: {linked_hotkeys}[/green]")
    console.print(f"  Total command runs: {total_commands}")
    console.print(f"  [green]Successful commands: {successful_commands}[/green]")
    console.print(f"  [red]Failed commands: {failed_commands}[/red]")
    
    # Per-hotkey summary table
    if show_table:
        table = Table(title="Hotkey Rotation Summary", box=box.ROUNDED)
        table.add_column("Hotkey", style="cyan")
        table.add_column("Linked", justify="center")
        table.add_column("Successful", justify="right", style="green")
        table.add_column("Failed", justify="right", style="red")
        table.add_column("Total", justify="right")
        
        for hotkey, result in results.items():
            if result["linked"]:
                successful = sum(cr["success"] for cr in result["command_results"])
                failed = len(result["command_results"]) - successful
                total = len(result["command_results"])
                table.add_row(
                    hotkey,
                    "[green]✓[/green]",
                    str(successful),
                    str(failed),
                    str(total),
                )
            else:
                table.add_row(hotkey, "[red]✗[/red]", "0", "0", "0")
        
        console.print("\n")
        console.print(table)
    
    return linked_hotkeys, successful_commands


def run_hotkey_rotation_mode(args, hotkeys: List[str], wallet: str, command: str, repetitions: int):
    """Run hotkey rotation mode and return results."""
    if not hotkeys:
        console.print("[red]Error: No hotkeys specified. Use --hotkeys or edit HOTKEY_LIST in config.[/red]")
        sys.exit(1)
    
    bot = CommandBot(
        max_retries=args.max_retries,
        retry_delay=args.retry_delay,
        show_output=not args.no_output,
    )
    
    results = bot.run_with_hotkey_rotation(
        hotkeys=hotkeys,
        wallet=wallet,
        command=command,
        repetitions=repetitions,
    )
    
    linked_hotkeys, successful_commands = show_hotkey_rotation_summary(results, args.summary)
    
    # Exit with error if any hotkey failed to link or all commands failed
    if linked_hotkeys == 0 or successful_commands == 0:
        sys.exit(1)
    else:
        sys.exit(0)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Command Bot - Execute terminal commands with automatic retry",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run a single command with retries
  python command_bot.py "apex link --wallet mama --hotkey go_8"
  
  # Run multiple commands
  python command_bot.py -c "ls -la" -c "pwd" -c "echo hello"
  
  # Custom retry settings
  python command_bot.py --max-retries 5 --retry-delay 2.0 "some-command"
  
  # Run from file
  python command_bot.py --file commands.txt
  
  # Hotkey rotation mode (uses config from top of file)
  python command_bot.py --hotkey-rotation
  
  # Hotkey rotation with overrides
  python command_bot.py --hotkey-rotation --hotkeys go_7 go_8 --repetitions 4
        """,
    )
    
    parser.add_argument(
        "command",
        nargs="*",
        help="Command(s) to execute",
    )
    parser.add_argument(
        "-c", "--command",
        action="append",
        dest="commands",
        help="Additional command to execute (can be used multiple times)",
    )
    parser.add_argument(
        "-f", "--file",
        help="Read commands from file (one per line)",
    )
    parser.add_argument(
        "-r", "--max-retries",
        type=int,
        default=3,
        help="Maximum number of retry attempts (default: 3)",
    )
    parser.add_argument(
        "-d", "--retry-delay",
        type=float,
        default=1.0,
        help="Delay in seconds between retries (default: 1.0)",
    )
    parser.add_argument(
        "--no-output",
        action="store_true",
        help="Don't show command output",
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue executing remaining commands even if one fails",
    )
    parser.add_argument(
        "--shell",
        action="store_true",
        help="Execute commands in shell",
    )
    parser.add_argument(
        "--cwd",
        help="Working directory for commands",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        default=True,
        help="Show execution summary (default: True)",
    )
    parser.add_argument(
        "--hotkey-rotation",
        action="store_true",
        help="Use hotkey rotation mode (cycles through hotkeys from config)",
    )
    parser.add_argument(
        "--hotkeys",
        nargs="+",
        help="Override hotkey list (use with --hotkey-rotation)",
    )
    parser.add_argument(
        "--wallet",
        help="Override wallet name (use with --hotkey-rotation)",
    )
    parser.add_argument(
        "--rotation-command",
        help="Override command to run (use with --hotkey-rotation)",
    )
    parser.add_argument(
        "--repetitions",
        type=int,
        help="Override number of repetitions per hotkey (use with --hotkey-rotation)",
    )
    
    args = parser.parse_args()
    
    # Hotkey rotation mode
    if args.hotkey_rotation:
        hotkeys = args.hotkeys if args.hotkeys else HOTKEY_LIST
        wallet = args.wallet if args.wallet else WALLET_NAME
        command = args.rotation_command if args.rotation_command else COMMAND_TO_RUN
        repetitions = args.repetitions if args.repetitions else REPETITIONS_PER_HOTKEY
        run_hotkey_rotation_mode(args, hotkeys, wallet, command, repetitions)
    
    # Normal command mode
    
    # Collect commands
    commands = []
    
    if args.file:
        try:
            with open(args.file, "r") as f:
                commands.extend(line.strip() for line in f if line.strip() and not line.startswith("#"))
        except FileNotFoundError:
            console.print(f"[red]Error: File '{args.file}' not found[/red]")
            sys.exit(1)
    
    if args.command:
        commands.extend(args.command)
    
    if args.commands:
        commands.extend(args.commands)
    
    if not commands:
        # If no commands provided and hotkey rotation not explicitly requested,
        # check if we should default to hotkey rotation mode
        if HOTKEY_LIST:
            console.print("[yellow]No commands provided. Defaulting to hotkey rotation mode...[/yellow]\n")
            hotkeys = args.hotkeys if args.hotkeys else HOTKEY_LIST
            wallet = args.wallet if args.wallet else WALLET_NAME
            command = args.rotation_command if args.rotation_command else COMMAND_TO_RUN
            repetitions = args.repetitions if args.repetitions else REPETITIONS_PER_HOTKEY
            run_hotkey_rotation_mode(args, hotkeys, wallet, command, repetitions)
        else:
            parser.print_help()
            sys.exit(1)
    
    # Create bot
    bot = CommandBot(
        max_retries=args.max_retries,
        retry_delay=args.retry_delay,
        show_output=not args.no_output,
    )
    
    # Run commands
    console.print(Panel(
        f"[bold]Command Bot[/bold]\n"
        f"Commands: {len(commands)}\n"
        f"Max retries: {args.max_retries}\n"
        f"Retry delay: {args.retry_delay}s",
        title="Configuration",
        border_style="blue",
    ))
    
    results = bot.run_commands(
        commands,
        shell=args.shell,
        cwd=args.cwd,
        stop_on_error=not args.continue_on_error,
    )
    
    # Show summary
    if args.summary:
        bot.show_summary()
    
    # Exit with error if any command failed
    if any(exit_code != 0 for exit_code, _, _ in results):
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()

