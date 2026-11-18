#!/bin/sh
set -eu
test "$(ls /sys/class/net | tr '\n' ' ')" = "lo "
mkdir /tmp/lab
openssl req -x509 -newkey rsa:2048 -nodes -days 1 -keyout /tmp/lab/key.pem -out /tmp/lab/cert.pem \
    -subj '/CN=factory.test' -addext 'subjectAltName=DNS:factory.test' 2>/tmp/lab/keygen.log
chmod 644 /tmp/lab/key.pem /tmp/lab/cert.pem
# These are ONLY aliases on lo inside --network none; no external route.
for address in 93.184.216.20 93.184.216.21 93.184.216.53 169.254.169.254 10.77.0.2; do
    ip address add "$address/32" dev lo
done
ip link set lo up
for tool in iptables ip6tables; do
    "$tool" -P OUTPUT DROP
    "$tool" -P INPUT DROP
    "$tool" -P FORWARD DROP
done
iptables -A OUTPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
iptables -A INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
iptables -A OUTPUT -d 93.184.216.20 -p tcp -m multiport --dports 80,443 -j ACCEPT
iptables -A INPUT -d 93.184.216.20 -p tcp -m multiport --dports 80,443 -j ACCEPT
for protocol in tcp udp; do
    iptables -A OUTPUT -d 93.184.216.53 -p "$protocol" --dport 53 -j ACCEPT
    iptables -A INPUT -d 93.184.216.53 -p "$protocol" --dport 53 -j ACCEPT
done
ip address show
ip route show
iptables-save
ip6tables-save
exec setpriv --reuid=65532 --regid=65532 --clear-groups --no-new-privs \
    --bounding-set=-all --inh-caps=-all --ambient-caps=-all \
    python -B -m integration.l2_launch.security.lab --child
