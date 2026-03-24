output "instance_ip" {
  description = "Elastic IP address of the GetVul instance"
  value       = aws_eip.getvul.public_ip
}

output "instance_id" {
  description = "EC2 instance ID"
  value       = aws_instance.getvul.id
}

output "ssh_command" {
  description = "SSH command to connect to the instance"
  value       = "ssh ubuntu@${aws_eip.getvul.public_ip}"
}

output "app_url" {
  description = "Application URL"
  value       = "https://${aws_eip.getvul.public_ip}"
}
