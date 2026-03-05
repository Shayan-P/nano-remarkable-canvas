#!/bin/bash
# Network scanner for 192.168.1.* subnet

check_ssh() {
    timeout 1 bash -c "echo > /dev/tcp/$1/22" 2>/dev/null && echo "✓" || echo "✗"
}

echo "IP Address       MAC Address          Hostname                         SSH"
echo "============================================================================"

arp -a | grep "192.168.1" | awk '{
    ip = $2
    gsub(/[()]/,"", ip)
    mac = $4
    hostname = $1
    if (hostname == "?") hostname = "(no hostname)"
    print ip "|" mac "|" hostname
}' | sort -t. -k4 -n | while IFS='|' read ip mac hostname; do
    ip=$(echo "$ip" | xargs)
    mac=$(echo "$mac" | xargs)
    hostname=$(echo "$hostname" | xargs)
    ssh_status=$(check_ssh "$ip")
    printf "%-16s %-20s %-32s %s\n" "$ip" "$mac" "$hostname" "$ssh_status"
done
