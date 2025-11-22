# Ansible Deployment

Use this scaffold to configure controller and agent nodes.

## Prerequisites
- SSH access to targets listed in `infra/inventory.ini`
- Ansible installed on the control machine (`pip install ansible`), or use the project `requirements.txt`

## Quickstart
1. Edit `infra/inventory.ini` and set `ansible_host` and `ansible_user` for your nodes.
2. Run all roles:
   - `ansible-playbook infra/site.yml`
3. Limit to specific hosts or roles:
   - Controller only: `ansible-playbook infra/site.yml --tags controller`
   - Agents only: `ansible-playbook infra/site.yml --tags agent` or `--limit agents`.

## Variables
Defaults live in `infra/group_vars/all.yml`:
- `project_dir`: install path (default `/opt/network-bug-triage`)
- `venv_dir`: virtualenv path
- `controller_args`: passed to `controller/processor.py` (defaults to `--dry-run`)
- `kafka_bootstrap`: controller Kafka bootstrap string
- `repo_sync_excludes`: patterns excluded during rsync from the repo

## What gets installed
- System packages for Python/rsync (Debian family)
- Repository synced to `project_dir`
- Virtualenv with `requirements.txt` installed
- systemd units:
  - `network-triage-controller.service`
  - `network-triage-agent.service`

## Logs
- Ansible logs to `logs/ansible.log` (from `ansible.cfg`).
