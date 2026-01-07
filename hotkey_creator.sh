#!/bin/bash

# Script to create multiple hotkeys for a given coldkey wallet
# Usage: ./create_multihotkey.sh <coldkey_name> <hotkey1> <hotkey2> ...

NUM_WORDS=12  # Default number of words

# Check if at least 2 arguments provided (coldkey + at least 1 hotkey)
if [ $# -lt 2 ]; then
    echo "Usage: $0 <coldkey_name> <hotkey1> [hotkey2] [hotkey3] ..."
    echo "Example: $0 mama apex1 apex2 apex3"
    exit 1
fi

COLDKEY_NAME="$1"
shift  # Remove first argument, leaving only hotkey names

echo "================================================"
echo "Creating multiple hotkeys for coldkey: $COLDKEY_NAME"
echo "Number of words: $NUM_WORDS"
echo "Hotkeys to create: $@"
echo "================================================"
echo ""

# Store all mnemonics for backup
MNEMONIC_FILE="mnemonics_${COLDKEY_NAME}_$(date +%Y%m%d_%H%M%S).txt"
echo "Mnemonics for coldkey: $COLDKEY_NAME" > "$MNEMONIC_FILE"
echo "Created: $(date)" >> "$MNEMONIC_FILE"
echo "========================================" >> "$MNEMONIC_FILE"

# Loop through each hotkey name
for HOTKEY_NAME in "$@"; do
    echo "Creating hotkey: $HOTKEY_NAME"
    echo "----------------------------------------"
    
    # Run btcli with automated input
    OUTPUT=$(printf "%s\n%s\n%s\n" "$COLDKEY_NAME" "$HOTKEY_NAME" "$NUM_WORDS" | btcli w new_hotkey 2>&1)
    
    echo "$OUTPUT"
    
    # Extract and save mnemonic
    MNEMONIC=$(echo "$OUTPUT" | grep -oP "The mnemonic to the new hotkey is: \K.*")
    if [ -n "$MNEMONIC" ]; then
        echo "" >> "$MNEMONIC_FILE"
        echo "Hotkey: $HOTKEY_NAME" >> "$MNEMONIC_FILE"
        echo "Mnemonic: $MNEMONIC" >> "$MNEMONIC_FILE"
        echo "✓ Hotkey '$HOTKEY_NAME' created successfully"
    else
        echo "✗ Failed to create hotkey '$HOTKEY_NAME'"
    fi
    
    echo ""
done

echo "================================================"
echo "All hotkeys processed!"
echo "Mnemonics saved to: $MNEMONIC_FILE"
echo ""
echo "⚠️  IMPORTANT: Store the mnemonic file securely and offline!"
echo "================================================"

