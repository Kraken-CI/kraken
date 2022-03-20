1. open URL from pulumi
2. login using admin/admin
3. go to settings
3.a) General tab:
   - set Kraken Server URL to URL from Pulumi
   - set ClickHouse Proxy Address from Pulumi
3.b) Cloud tab:
   - in Amazon Web Services pane set Access Key and Secret Access Key
4. Go to Agents ->  Groups and create a group with deployment to ECS Fargate
4.a) Fill Region
4.b) From ECS service in AWS console, from any page of Kraken ECS service copy and paste info about
   - Cluster name
   - Subnets
   - Security Groups
5. Go to Demo project and its Master branch management page and switch the worklflow jobs to newly created ecs agents group
6. Run CI flow
