# SBOM2CVE Terraform Outputs

output "k3s_server_public_ip" {
  description = "Public IP of K3s server (control plane)"
  value       = aws_eip.k3s_server.public_ip
}

output "k3s_server_private_ip" {
  description = "Private IP of K3s server"
  value       = aws_instance.k3s_server.private_ip
}

output "k3s_agent_public_ips" {
  description = "Public IPs of K3s agent nodes"
  value       = aws_instance.k3s_agent[*].public_ip
}

output "k3s_agent_private_ips" {
  description = "Private IPs of K3s agent nodes"
  value       = aws_instance.k3s_agent[*].private_ip
}

output "vex_api_alb_dns" {
  description = "DNS name of VEX API Application Load Balancer"
  value       = var.enable_alb ? aws_lb.vex_api[0].dns_name : "ALB disabled"
}

output "vex_api_alb_url" {
  description = "Full URL of VEX API via ALB"
  value       = var.enable_alb ? "http://${aws_lb.vex_api[0].dns_name}" : "ALB disabled"
}

output "ssh_command_server" {
  description = "SSH command to connect to K3s server"
  value       = "ssh -i ~/.ssh/id_rsa ubuntu@${aws_eip.k3s_server.public_ip}"
}

output "ssh_command_agents" {
  description = "SSH commands to connect to K3s agents"
  value = [
    for i, ip in aws_instance.k3s_agent[*].public_ip :
    "ssh -i ~/.ssh/id_rsa ubuntu@${ip}  # agent-${i + 1}"
  ]
}

output "kubeconfig_command" {
  description = "Command to get kubeconfig from server"
  value       = "scp -i ~/.ssh/id_rsa ubuntu@${aws_eip.k3s_server.public_ip}:/etc/rancher/k3s/k3s.yaml ~/.kube/sbom2cve-config"
}

output "kubectl_setup_commands" {
  description = "Commands to set up kubectl access"
  value = <<-EOT
    # 1. Copy kubeconfig from server
    scp -i ~/.ssh/id_rsa ubuntu@${aws_eip.k3s_server.public_ip}:/etc/rancher/k3s/k3s.yaml ~/.kube/sbom2cve-config

    # 2. Update server IP in kubeconfig
    sed -i '' 's/127.0.0.1/${aws_eip.k3s_server.public_ip}/g' ~/.kube/sbom2cve-config

    # 3. Set KUBECONFIG environment variable
    export KUBECONFIG=~/.kube/sbom2cve-config

    # 4. Verify connection
    kubectl get nodes
  EOT
}

output "cluster_info" {
  description = "Cluster information summary"
  value = {
    cluster_name      = var.cluster_name
    environment       = var.environment
    region            = var.aws_region
    server_instance   = var.server_instance_type
    agent_instances   = var.agent_instance_type
    agent_count       = var.agent_count
    vpc_id            = aws_vpc.main.id
    security_group_id = aws_security_group.k3s.id
  }
}

output "next_steps" {
  description = "Next steps after deployment"
  value = <<-EOT
    ========================================
    SBOM2CVE AWS Deployment Complete!
    ========================================

    1. SSH to K3s server:
       ssh -i ~/.ssh/id_rsa ubuntu@${aws_eip.k3s_server.public_ip}

    2. Check K3s status:
       ssh ubuntu@${aws_eip.k3s_server.public_ip} 'sudo kubectl get nodes'

    3. Set up local kubectl access:
       ${self.kubectl_setup_commands}

    4. Deploy SBOM2CVE stack:
       kubectl apply -f k8s/

    5. Access VEX API:
       ${var.enable_alb ? "http://${aws_lb.vex_api[0].dns_name}/health" : "kubectl port-forward svc/vex-api 8080:80 -n sbom2cve"}

    For detailed deployment instructions, see:
    https://github.com/8BitTacoSupreme/sbom2cve/blob/future-state-mvp/DEPLOYMENT.md
  EOT
}
