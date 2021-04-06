terraform {
  required_providers {
    aws = {
      source = "hashicorp/aws"
      version = "~> 3.27"
    }
  }
}

provider "aws" {
  profile = "default"
  region = "{{ region }}"
}

data "aws_availability_zones" "available" {}

resource "aws_vpc" "Vpc" {
  assign_generated_ipv6_cidr_block = true
  enable_dns_support = true
  enable_dns_hostnames = true

  cidr_block = "{{ vpcCidr }}"

  tags = {
    Name = "{{ account }}"
    TMHCC_TestOwner = var.TMHCC_TechOwner
  }
}

resource "aws_vpc_dhcp_options_association" "DhcpOptions" {
  vpc_id = aws_vpc.Vpc.id
  dhcp_options_id = "{{ dhcpOptionsId }}"
}

resource "aws_subnet" "TransitSubnet" {
  count = 2
  vpc_id = aws_vpc.Vpc.id
  availability_zone = data.aws_availability_zones.available.names[count.index]
  assign_ipv6_address_on_creation = true
  map_public_ip_on_launch = false
  cidr_block = cidrsubnet("{{ vpcCidr }}", 6, 15 - count.index)
  ipv6_cidr_block = cidrsubnet(aws_vpc.Vpc.ipv6_cidr_block, 8, count.index + 1)

  tags = {
    Name = "{{ account }} Transit subnet AZ ${data.aws_availability_zones.available.names[count.index]}"
  }
}

resource "aws_subnet" "PrivateSubnet" {
  count = 2
  vpc_id = aws_vpc.Vpc.id
  availability_zone = data.aws_availability_zones.available.names[count.index]
  assign_ipv6_address_on_creation = false
  map_public_ip_on_launch = false
  cidr_block = cidrsubnet("{{ vpcCidr }}", 2, count.index + 1)

  tags = {
    Name = "{{ account }} Private subnet AZ ${data.aws_availability_zones.available.names[count.index]}"
  }
}

resource "aws_ec2_transit_gateway_vpc_attachment" "TransitGatewayAttachment" {
  vpc_id = aws_vpc.Vpc.id
  transit_gateway_id = "{{ transitGatewayId }}"
  subnet_ids = aws_subnet.TransitSubnet[*].id
  ipv6_support = "enable"
  transit_gateway_default_route_table_association = false

  tags = {
    Name = "{{ account }} VPC attachment"
  }
}

resource "aws_route_table" "PrivateRouteTable" {
  count = 2
  vpc_id = aws_vpc.Vpc.id

  route {
    cidr_block = "0.0.0.0/0"
    transit_gateway_id = "{{ transitGatewayId }}"
  }

  route {
    ipv6_cidr_block = "::/0"
    transit_gateway_id = "tgw-06173001949ff1ea2"
  }

  tags = {
    Name = "{{ account }} Private routes AZ ${data.aws_availability_zones.available.names[count.index]}"
  }
}

resource "aws_route_table_association" "TransitSubnetRouteTableAssociation" {
  count = 2
  subnet_id = aws_subnet.TransitSubnet[count.index].id
  route_table_id = aws_route_table.PrivateRouteTable[count.index].id
}

resource "aws_route_table_association" "PrivateSubnetRouteTableAssociation" {
  count = 2
  subnet_id = aws_subnet.PrivateSubnet[count.index].id
  route_table_id = aws_route_table.PrivateRouteTable[count.index].id
}

resource "aws_ec2_transit_gateway_route_table" "TransitGatewayRouteTable" {
  transit_gateway_id = "{{ transitGatewayId }}"
  
  tags = {
    Name = "{{ account }} Route Table"
  }
}

resource "aws_ec2_transit_gateway_route" "TransitGatewayRouteTableDefaultIpv4Route" {
  destination_cidr_block = "0.0.0.0/0"
  transit_gateway_attachment_id = aws_ec2_transit_gateway_vpc_attachment.TransitGatewayAttachment.id
  transit_gateway_route_table_id = aws_ec2_transit_gateway_route_table.TransitGatewayRouteTable.id
}

resource "aws_ec2_transit_gateway_route" "TransitGatewayRouteTableDefaultIpv6Route" {
  destination_cidr_block = "::/0"
  transit_gateway_attachment_id = aws_ec2_transit_gateway_vpc_attachment.TransitGatewayAttachment.id
  transit_gateway_route_table_id = aws_ec2_transit_gateway_route_table.TransitGatewayRouteTable.id
}

resource "aws_ec2_transit_gateway_route_table_association" "TransitGatewayRouteTableAssociation" {
  transit_gateway_attachment_id = aws_ec2_transit_gateway_vpc_attachment.TransitGatewayAttachment.id
  transit_gateway_route_table_id = aws_ec2_transit_gateway_route_table.TransitGatewayRouteTable.id
}

resource "aws_ec2_transit_gateway_route_table_propagation" "TransitGatewayInspectionRouteTablePropagation" {
  transit_gateway_attachment_id  = aws_ec2_transit_gateway_vpc_attachment.TransitGatewayAttachment.id
  transit_gateway_route_table_id = "{{ transitGatewayInspectionRouteTable }}"
}

resource "aws_security_group" "SgAnyAny" {
  vpc_id = aws_vpc.Vpc.id
  name = "PermitAnyAny-SG"
  description = "Permit all traffic"

  ingress {
    from_port = 0
    to_port = 0
    protocol = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    ipv6_cidr_blocks = ["::/0"]
  }

  egress {
    from_port = 0
    to_port = 0
    protocol = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    ipv6_cidr_blocks = ["::/0"]
  }

  tags = {
    Name = "Permit all traffic"
  }
}
