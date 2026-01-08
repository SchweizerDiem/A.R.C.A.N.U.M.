#!/bin/bash

# Script to create Prosody accounts for the Multi-Agent Traffic Control System
# Usage: sudo ./create_prosody_accounts.sh

# Function to create an account
create_account() {
    local user=$1
    local password=$2
    if sudo prosodyctl register "$user" localhost "$password"; then
        echo "Created account: $user@localhost"
    else
        echo "Failed to create account (or already exists): $user@localhost"
    fi
}

echo "Creating Prosody accounts..."

# Monitor Agent
create_account "monitor" "123"

# Disruption Agent
create_account "disruption" "123"

# Ambulance Agent
create_account "ambulance" "123"

# Traffic Light Agents (1-6)
for i in {1..6}; do
    create_account "semaforo_$i" "123"
done

# Car Agents (1-20)
for i in {1..20}; do
    create_account "carro_$i" "123"
done

echo "All accounts processed."
