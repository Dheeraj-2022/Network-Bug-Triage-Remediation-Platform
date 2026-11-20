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

## Remediation playbooks and the safety boundary
The remediation playbooks in `infra/playbooks/` are only ever invoked by
`controller/remediation/executors.py`, after a proposal has been previewed and
approved through the shared remediation policy. The processor never calls them
directly.

- Real execution requires the proposal to have been previewed in
  `NBT_REMEDIATION_MODE=ansible` mode (or `processor.py --execute`) **and** the
  approving process to run in the same mode. Default mode is `simulate`.
- In `ansible` mode, target hosts must also appear (uncommented) in the
  `[agents]` group of `infra/inventory.ini`.
- Variables are constructed by the policy from validated values (interface names,
  integer MTU in 1280–9216, allowlisted driver modules); free text is never passed.
  The playbooks additionally `quote` interpolated shell arguments.
- Failures are recorded; no automatic retry or rollback playbook is run.
- Keep `controller_args: --dry-run` unless you intend real changes on an isolated testbed.
