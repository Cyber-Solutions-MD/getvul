# GetVul — Azure infrastructure
# Single VM running Docker Compose with auto-update

terraform {
  required_version = ">= 1.7"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }
}

provider "azurerm" {
  features {}
}

# -- Resource Group --

resource "azurerm_resource_group" "getvul" {
  name     = "getvul-rg"
  location = var.location

  tags = {
    environment = "production"
    managed_by  = "terraform"
  }
}

# -- Virtual Network --

resource "azurerm_virtual_network" "getvul" {
  name                = "getvul-vnet"
  address_space       = ["10.0.0.0/16"]
  location            = azurerm_resource_group.getvul.location
  resource_group_name = azurerm_resource_group.getvul.name

  tags = {
    environment = "production"
    managed_by  = "terraform"
  }
}

resource "azurerm_subnet" "getvul" {
  name                 = "getvul-subnet"
  resource_group_name  = azurerm_resource_group.getvul.name
  virtual_network_name = azurerm_virtual_network.getvul.name
  address_prefixes     = ["10.0.1.0/24"]
}

# -- Network Security Group --

resource "azurerm_network_security_group" "getvul" {
  name                = "getvul-nsg"
  location            = azurerm_resource_group.getvul.location
  resource_group_name = azurerm_resource_group.getvul.name

  security_rule {
    name                       = "allow-http"
    priority                   = 100
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "80"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }

  security_rule {
    name                       = "allow-https"
    priority                   = 110
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "443"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }

  security_rule {
    name                       = "allow-ssh"
    priority                   = 120
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "22"
    source_address_prefixes    = var.ssh_allowed_cidrs
    destination_address_prefix = "*"
  }

  tags = {
    environment = "production"
    managed_by  = "terraform"
  }
}

# -- Public IP --

resource "azurerm_public_ip" "getvul" {
  name                = "getvul-pip"
  location            = azurerm_resource_group.getvul.location
  resource_group_name = azurerm_resource_group.getvul.name
  allocation_method   = "Static"
  sku                 = "Standard"

  tags = {
    environment = "production"
    managed_by  = "terraform"
  }
}

# -- Network Interface --

resource "azurerm_network_interface" "getvul" {
  name                = "getvul-nic"
  location            = azurerm_resource_group.getvul.location
  resource_group_name = azurerm_resource_group.getvul.name

  ip_configuration {
    name                          = "internal"
    subnet_id                     = azurerm_subnet.getvul.id
    private_ip_address_allocation = "Dynamic"
    public_ip_address_id          = azurerm_public_ip.getvul.id
  }

  tags = {
    environment = "production"
    managed_by  = "terraform"
  }
}

resource "azurerm_network_interface_security_group_association" "getvul" {
  network_interface_id      = azurerm_network_interface.getvul.id
  network_security_group_id = azurerm_network_security_group.getvul.id
}

# -- Linux Virtual Machine --

resource "azurerm_linux_virtual_machine" "getvul" {
  name                = "getvul-vm"
  location            = azurerm_resource_group.getvul.location
  resource_group_name = azurerm_resource_group.getvul.name
  size                = var.vm_size
  admin_username      = var.admin_username

  network_interface_ids = [
    azurerm_network_interface.getvul.id,
  ]

  admin_ssh_key {
    username   = var.admin_username
    public_key = var.ssh_public_key
  }

  os_disk {
    caching              = "ReadWrite"
    storage_account_type = "Premium_LRS"
    disk_size_gb         = var.disk_size_gb
  }

  source_image_reference {
    publisher = "Canonical"
    offer     = "0001-com-ubuntu-server-jammy"
    sku       = "22_04-lts-gen2"
    version   = "latest"
  }

  custom_data = base64encode(templatefile("${path.module}/startup.sh", {
    app_name    = "getvul"
    github_repo = var.github_repo
    deploy_key  = var.deploy_key
  }))

  disable_password_authentication = true

  tags = {
    environment = "production"
    managed_by  = "terraform"
  }
}
