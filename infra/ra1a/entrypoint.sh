#!/bin/sh
set -eu
# Must be launched with --network none. All globally-looking IPs below are aliases
# in this disposable namespace, not actual Internet targets. No host networking.
test "$(ls /sys/class/net | tr '\n' ' ')" = "lo "
mkdir /tmp/lab
openssl req -x509 -newkey rsa:2048 -nodes -days 1 \
    -keyout /tmp/lab/key.pem -out /tmp/lab/cert.pem -subj '/CN=factory.test' \
    -addext 'subjectAltName=DNS:factory.test' 2>/tmp/lab/cert-generation.log
chmod 644 /tmp/lab/key.pem /tmp/lab/cert.pem
for address in 93.184.216.20 93.184.216.21 93.184.216.53 169.254.169.254 10.77.0.2; do
    ip address add "$address/32" dev lo
done
ip link set lo up
iptables -P OUTPUT DROP
iptables -P INPUT DROP
iptables -P FORWARD DROP
ip6tables -P OUTPUT DROP
ip6tables -P INPUT DROP
ip6tables -P FORWARD DROP
iptables -A OUTPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
iptables -A INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
iptables -A OUTPUT -d 93.184.216.20 -p tcp -m multiport --dports 80,443 -j ACCEPT
iptables -A INPUT -d 93.184.216.20 -p tcp -m multiport --dports 80,443 -j ACCEPT
iptables -A OUTPUT -d 93.184.216.53 -p udp --dport 53 -j ACCEPT
iptables -A INPUT -d 93.184.216.53 -p udp --dport 53 -j ACCEPT
iptables -A OUTPUT -d 93.184.216.53 -p tcp --dport 53 -j ACCEPT
iptables -A INPUT -d 93.184.216.53 -p tcp --dport 53 -j ACCEPT
echo '=== ISOLATED NAMESPACE AND FIREWALL ==='
ip address show
ip route show
iptables-save
ip6tables-save
# Root is setup-only. Collector/tests cannot alter routes/firewall or gain privilege.
exec setpriv --reuid=65532 --regid=65532 --clear-groups --no-new-privs \
    --bounding-set=-all --inh-caps=-all --ambient-caps=-all \
    python scripts/verify_ra1a.py /tmp/verification
