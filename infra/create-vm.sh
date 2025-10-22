#!/usr/bin/env bash
#
# infra/create-vm.sh
#
# Create a multi-VM testbed using Vagrant (VirtualBox by default).
# - Generates Vagrantfile for a simple ToR-like topology (Linux bridges can be added manually)
# - Optionally runs `vagrant up` (commented out by default)
# - Generates a basic inventory.ini for Ansible at infra/inventory.ini
#
# Usage:
#   ./create-vm.sh [NUM_NODES] [--up]
#
# Examples:
#   ./create-vm.sh 5
#   ./create-vm.sh 7 --up
#
set -euo pipefail

NUM_NODES=${1:-5}
DO_VAGRANT_UP=false
if [[ "${2:-}" == "--up" ]]; then
  DO_VAGRANT_UP=true
fi

WORKDIR="$(cd "$(dirname "$0")" && pwd)"
VAGRANTFILE="${WORKDIR}/Vagrantfile"
INVENTORY="${WORKDIR}/inventory.ini"

BOX="${BOX:-generic/ubuntu2010}"   # change if you have another base box
BASE_IP="192.168.56"              # VirtualBox host-only network range (adjust if conflict)

echo "Creating Vagrantfile for ${NUM_NODES} nodes at ${VAGRANTFILE}"

cat > "${VAGRANTFILE}" <<'VAGRANT'
# Auto-generated Vagrantfile
Vagrant.configure("2") do |config|
  config.vm.box = "__BOX__"
  config.vm.synced_folder ".", "/vagrant", disabled: true

  (1..__NUM_NODES__).each do |i|
    config.vm.define "node#{i}" do |node|
      host_ip = "__BASE_IP__." + (100 + i).to_s
      node.vm.hostname = "node#{i}"
      node.vm.network "private_network", ip: host_ip

      node.vm.provider "virtualbox" do |vb|
        vb.name = "nbt-node#{i}"
        vb.memory = 2048
        vb.cpus = 1
      end

      node.vm.provision "shell", inline: <<-SHELL
        set -e
        # minimal packages for provisioning
        apt-get update -y
        apt-get install -y python3 python3-venv python3-pip git iproute2 net-tools tcpdump
      SHELL
    end
  end
end
VAGRANT

# Replace placeholders
perl -pi -e "s/__NUM_NODES__/${NUM_NODES}/g" "${VAGRANTFILE}"
perl -pi -e "s#__BOX__#${BOX}#g" "${VAGRANTFILE}"
perl -pi -e "s/__BASE_IP__/${BASE_IP}/g" "${VAGRANTFILE}"

echo "Writing Ansible inventory template to ${INVENTORY}"
cat > "${INVENTORY}" <<INVENT
# infra/inventory.ini - auto-generated template
[all]
# Replace with the IPs assigned to VMs (or hostnames)
# node1 ansible_host=192.168.56.101 ansible_user=vagrant
# node2 ansible_host=192.168.56.102 ansible_user=vagrant

[controllers]
# controller ansible_host=192.168.56.200 ansible_user=ubuntu

[agents:children]
all
INVENT

echo ""
echo "Vagrantfile and inventory template created."
echo "To bring up the VMs (requires Vagrant + VirtualBox):"
echo "  cd ${WORKDIR} && vagrant up"
if [ "${DO_VAGRANT_UP}" = true ]; then
  echo "Running 'vagrant up' now..."
  (cd "${WORKDIR}" && vagrant up)
fi

echo ""
echo "After VMs are up, edit infra/inventory.ini to add ansible_host lines (IPs shown in 'vagrant ssh-config'),"
echo "then run:"
echo "  ansible-playbook -i infra/inventory.ini infra/provision.yml"
