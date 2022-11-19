import pulumi
from pulumi import export, ResourceOptions
import pulumi_aws as aws
import json


KK_VER = '0.894'


def kk_service(cluster, role, prv_dns_ns, vpc_subnets, secgrp, loggrp, name, image, cntr_count, port, proto='tcp', env=None, web_listener=None, target_group=None):
    if env is None:
        env = []
    outputs = pulumi.Output.all(
        env=env,
        loggrp=loggrp.name)

    container_definitions = outputs.apply(lambda args: json.dumps([{
        'name': name,
        'image': image,
        'portMappings': [{
            'containerPort': port,
            'hostPort': port,
            'protocol': proto
        }],
        "environment": args['env'],
        "logConfiguration": {
            "logDriver": "awslogs",
            "options": {
                "awslogs-group": args['loggrp'],
                "awslogs-region": 'ca-central-1',
                "awslogs-stream-prefix": name,
            },
        },
        'command': ['server', '--address', ':9999', '/data'] if name == 'minio' else None
    }]))

    # Spin up a load balanced service running our container image.
    td = aws.ecs.TaskDefinition('kk-task-%s' % name,
        family='%s-td' % name,
        cpu='256',
        memory='512',
        network_mode='awsvpc',
        requires_compatibilities=['FARGATE'],
        execution_role_arn=role.arn,
        container_definitions=container_definitions
    )

    sd_svc = aws.servicediscovery.Service(name,
                                          name=name,
                                          dns_config=aws.servicediscovery.ServiceDnsConfigArgs(
                                              namespace_id=prv_dns_ns.id,
                                              dns_records=[aws.servicediscovery.ServiceDnsConfigDnsRecordArgs(
                                                  ttl=10,
                                                  type="A",
                                              )],
                                              routing_policy="MULTIVALUE",
                                          ),
                                          health_check_custom_config=aws.servicediscovery.ServiceHealthCheckCustomConfigArgs(
                                              failure_threshold=1,
                                          ))

    if name == 'kk-ui':
        load_balancers = [aws.ecs.ServiceLoadBalancerArgs(
            target_group_arn=target_group.arn,
            container_name='kk-ui',
            container_port=port,
        )]
        opts = ResourceOptions(depends_on=[web_listener])
    else:
        load_balancers = None
        opts = None

    aws.ecs.Service('%s-svc' % name,
                    cluster=cluster.arn,
                    desired_count=cntr_count,
                    launch_type='FARGATE',
                    task_definition=td.arn,
                    service_registries=aws.ecs.ServiceServiceRegistriesArgs(
                        registry_arn=sd_svc.arn
                    ),
                    network_configuration=aws.ecs.ServiceNetworkConfigurationArgs(
                        assign_public_ip=True,
                        subnets=vpc_subnets.ids,
                        security_groups=[secgrp.id],
                    ),
                    load_balancers=load_balancers,
                    opts=opts)

    return sd_svc


def kk_image(svc, ver):
    if ':' in svc:
        svc = svc + '.'
    else:
        svc = svc + ':'
    return 'us-docker.pkg.dev/kraken-261806/kk/%s%s' % (svc, ver)


def main():
    kk_ver = KK_VER

    # Create an ECS cluster to run a container-based service.
    cluster = aws.ecs.Cluster('kraken-ci-21')

    # Read back the default VPC and public subnets, which we will use.
    default_vpc = aws.ec2.get_vpc(default=True)
    default_vpc_subnets = aws.ec2.get_subnet_ids(vpc_id=default_vpc.id)

    # Create a SecurityGroup that permits HTTP ingress and unrestricted egress.
    secgrp = aws.ec2.SecurityGroup('kk-secgrp',
                                   vpc_id=default_vpc.id,
                                   description='Enable HTTP access',
                                   ingress=[aws.ec2.SecurityGroupIngressArgs(
                                       protocol='tcp',
                                       from_port=80,
                                       to_port=80,
                                       cidr_blocks=['0.0.0.0/0'],
                                   ), aws.ec2.SecurityGroupIngressArgs( # pgsql
                                       protocol='tcp',
                                       from_port=5432,
                                       to_port=5432,
                                       cidr_blocks=['0.0.0.0/0'],
                                   ), aws.ec2.SecurityGroupIngressArgs( # redis
                                       protocol='tcp',
                                       from_port=6379,
                                       to_port=6379,
                                       cidr_blocks=['0.0.0.0/0'],
                                   ), aws.ec2.SecurityGroupIngressArgs( # clickhouse
                                       protocol='tcp',
                                       from_port=8123,
                                       to_port=8123,
                                       cidr_blocks=['0.0.0.0/0'],
                                   ), aws.ec2.SecurityGroupIngressArgs( # clickhouse 2 conn
                                       protocol='tcp',
                                       from_port=9000,
                                       to_port=9000,
                                       cidr_blocks=['0.0.0.0/0'],
                                   ), aws.ec2.SecurityGroupIngressArgs( # clickhouse proxy
                                       protocol='udp',
                                       from_port=9001,
                                       to_port=9001,
                                       cidr_blocks=['0.0.0.0/0'],
                                   ), aws.ec2.SecurityGroupIngressArgs( # planner
                                       protocol='tcp',
                                       from_port=7997,
                                       to_port=7997,
                                       cidr_blocks=['0.0.0.0/0'],
                                   ), aws.ec2.SecurityGroupIngressArgs( # server
                                       protocol='tcp',
                                       from_port=6363,
                                       to_port=6363,
                                       cidr_blocks=['0.0.0.0/0'],
                                   ), aws.ec2.SecurityGroupIngressArgs( # ui
                                       protocol='tcp',
                                       from_port=80,
                                       to_port=80,
                                       cidr_blocks=['0.0.0.0/0'],
                                   ), aws.ec2.SecurityGroupIngressArgs( # minio
                                       protocol='tcp',
                                       from_port=9999,
                                       to_port=9999,
                                       cidr_blocks=['0.0.0.0/0'],
                                   )],
                                   egress=[aws.ec2.SecurityGroupEgressArgs(
                                       protocol='-1',
                                       from_port=0,
                                       to_port=0,
                                       cidr_blocks=['0.0.0.0/0'],
                                   )],
                                   )

    # Create a load balancer to listen for HTTP traffic on port 80.
    alb = aws.lb.LoadBalancer('app-lb',
                              security_groups=[secgrp.id],
                              subnets=default_vpc_subnets.ids,
                              )

    atg = aws.lb.TargetGroup('app-tg',
                             port=80,
                             protocol='HTTP',
                             target_type='ip',
                             vpc_id=default_vpc.id,
                             )

    wl = aws.lb.Listener('web',
                         load_balancer_arn=alb.arn,
                         port=80,
                         default_actions=[aws.lb.ListenerDefaultActionArgs(
                             type='forward',
                             target_group_arn=atg.arn,
                         )],
                         )

    # Create an IAM role that can be used by our service's task.
    role = aws.iam.Role('task-exec-role',
                        assume_role_policy=json.dumps({
                            'Version': '2008-10-17',
                            'Statement': [{
                                'Sid': '',
                                'Effect': 'Allow',
                                'Principal': {
                                    'Service': 'ecs-tasks.amazonaws.com'
                                },
                                'Action': 'sts:AssumeRole',
                            }]
                        }),
                        )

    aws.iam.RolePolicyAttachment('task-exec-policy',
                                 role=role.name,
                                 policy_arn='arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy',
                                 )

    ####### service discovery stuff

    prv_dns_ns = aws.servicediscovery.PrivateDnsNamespace("kk-ns",
                                                          name="kk-ns",
                                                          description="kk-namespace",
                                                          vpc=default_vpc.id)
    ####### POSTGRES

    pgsql = aws.rds.Instance("pgsql",
                             allocated_storage=5,
                             engine="postgres",
                             engine_version="11",
                             instance_class="db.t3.micro",
                             name="kraken",
                             #parameter_group_name="default.mysql5.7",
                             username="kraken",
                             password="kk123kk4321",
                             skip_final_snapshot=True,
                             vpc_security_group_ids=[secgrp.id])

    ####### Minio / S3
    # TODO: postponed, regular minio instead for now
    # create a user to access s3
    # s3_user = aws.iam.User("s3-kk-user")
    # s3_access_key = aws.iam.AccessKey("s3AccessKey", user=s3_user.name)
    # s3_rw = aws.iam.UserPolicy("s3rw",
    #                            user=s3_user.name,
    #                            policy="""{
    #                            "Version": "2012-10-17",
    #                            "Statement": [
    #                              {
    #                                "Action": [
    #                                  "s3:*"
    #                                ],
    #                                "Effect": "Allow",
    #                                "Resource": "*"
    #                              }
    #                            ]
    #                            }
    #                            """)


    ####

    lg = aws.cloudwatch.LogGroup(
        "kk-log-group",
        retention_in_days=1,
    )


    ####### REDIS

    redis_sd = kk_service(cluster,
                          role,
                          prv_dns_ns,
                          default_vpc_subnets,
                          secgrp,
                          lg,
                          'redis',
                          'redis:alpine',
                          1,
                          6379)

    ####### MINIO

    minio_env = [
        { "name": "MINIO_ACCESS_KEY", "value": 'UFSEHRCFU4ACUEWHCHWU'  },
        { "name": "MINIO_SECRET_KEY", "value": 'HICSHuhIIUhiuhMIUHIUhGFfUHugy6fGJuyyfiGY'  },
    ]

    minio_sd = kk_service(cluster,
                          role,
                          prv_dns_ns,
                          default_vpc_subnets,
                          secgrp,
                          lg,
                          'minio',
                          'minio/minio:RELEASE.2020-12-18T03-27-42Z',
                          1,
                          9999,
                          env=minio_env)

    ####### CLICKHOUSE

    clickhouse_sd = kk_service(cluster,
                               role,
                               prv_dns_ns,
                               default_vpc_subnets,
                               secgrp,
                               lg,
                               'clickhouse',
                               kk_image('clickhouse-server:22.10.2.11', kk_ver),
                               1,
                               8123)

    ####### CLICKHOUSE PROXY

    chproxy_env = pulumi.Output.all(
        domain=prv_dns_ns.name,
        ch_addr=clickhouse_sd.name,    # clickhouse service addr
        ch_port="8123"                 # clickhouse service port
    ).apply(lambda args: [
        { "name": "KRAKEN_CLICKHOUSE_URL", "value": "http://%s.%s:%s/" % (args['ch_addr'], args['domain'], args['ch_port'])  },
    ])

    clickhouse_proxy_sd = kk_service(cluster,
                                     role,
                                     prv_dns_ns,
                                     default_vpc_subnets,
                                     secgrp,
                                     lg,
                                     'clickhouse-proxy',
                                     kk_image('kkchproxy', kk_ver),
                                     1,
                                     9001,
                                     proto='udp',
                                     env=chproxy_env)

    ####### KK CONTROLLER

    kk_ctrl_env = pulumi.Output.all(
        domain=prv_dns_ns.name,
        redis=redis_sd.name,
        pgsql=pgsql.endpoint,
        ch_proxy_port="9001",                # clickhouse proxy port
        ch_proxy_addr=clickhouse_proxy_sd.name,   # clickhouse proxy addr
        ch_addr=clickhouse_sd.name,    # clickhouse service addr
        ch_port="8123"                 # clickhouse service port
    ).apply(lambda args: [
        { "name": "KRAKEN_REDIS_ADDR", "value": "%s.%s" % (args['redis'], args['domain'])  },
        { "name": "KRAKEN_DB_URL", "value": "postgresql://kraken:kk123kk4321@%s/kraken" % args['pgsql']  },
        { "name": "KRAKEN_CLICKHOUSE_PORT", "value": args['ch_proxy_port']  },
        { "name": "KRAKEN_CLICKHOUSE_ADDR", "value": "%s.%s:%s" % (args['ch_proxy_addr'], args['domain'], args['ch_proxy_port'])  },
        { "name": "KRAKEN_CLICKHOUSE_URL", "value": "http://%s.%s:%s/" % (args['ch_addr'], args['domain'], args['ch_port'])  },
        { "name": "KRAKEN_SERVER_PORT", "value": "6363"  },
        { "name": "KRAKEN_SERVER_ADDR", "value": "server"  },
        { "name": "KRAKEN_PLANNER_URL", "value": "http://localhost:7997/"  },
    ])

    kk_controller_sd = kk_service(cluster,
                                  role,
                                  prv_dns_ns,
                                  default_vpc_subnets,
                                  secgrp,
                                  lg,
                                  'kk-controller',
                                  kk_image('kkcontroller', kk_ver),
                                  1,
                                  7997,
                                  env=kk_ctrl_env)

    ####### KK RQ

    kk_rq_env = pulumi.Output.all(
        domain=prv_dns_ns.name,
        redis=redis_sd.name,
        pgsql=pgsql.endpoint,
        ch_proxy_port="9001",                # clickhouse proxy port
        ch_proxy_addr=clickhouse_proxy_sd.name,   # clickhouse proxy addr
        planner=kk_controller_sd.name,
        minio=minio_sd.name,  # TODO 's3.ca-central-1.amazonaws.com:443',
        minio_access_key='UFSEHRCFU4ACUEWHCHWU',  # TODO s3_access_key.id,
        minio_secret_key='HICSHuhIIUhiuhMIUHIUhGFfUHugy6fGJuyyfiGY',  # TODO s3_access_key.secret
    ).apply(lambda args: [
        { "name": "KRAKEN_REDIS_ADDR", "value": "%s.%s" % (args['redis'], args['domain'])  },
        { "name": "KRAKEN_DB_URL", "value": "postgresql://kraken:kk123kk4321@%s/kraken" % args['pgsql']  },
        { "name": "KRAKEN_CLICKHOUSE_PORT", "value": args['ch_proxy_port']  },
        { "name": "KRAKEN_CLICKHOUSE_ADDR", "value": "%s.%s:%s" % (args['ch_proxy_addr'], args['domain'], args['ch_proxy_port'])  },
        { "name": "KRAKEN_PLANNER_URL", "value": "http://%s.%s:7997/" % (args['planner'], args['domain'])  },
        { "name": "KRAKEN_MINIO_ADDR", "value": '%s.%s:9999' % (args['minio'], args['domain'])  },
        { "name": "MINIO_ACCESS_KEY", "value": args['minio_access_key']  },
        { "name": "MINIO_SECRET_KEY", "value": args['minio_secret_key']  },
    ])

    kk_service(cluster,
               role,
               prv_dns_ns,
               default_vpc_subnets,
               secgrp,
               lg,
               'kk-rq',
               kk_image('kkrq', kk_ver),
               1,
               1234,  # not used
               env=kk_rq_env)

    ####### KK SERVER

    kk_srv_env = pulumi.Output.all(
        domain=prv_dns_ns.name,
        redis=redis_sd.name,
        pgsql=pgsql.endpoint,
        ch_proxy_port="9001",                # clickhouse proxy port
        ch_proxy_addr=clickhouse_proxy_sd.name,   # clickhouse proxy addr
        ch_addr=clickhouse_sd.name,    # clickhouse service addr
        ch_port="8123",                 # clickhouse service port
        planner=kk_controller_sd.name,
        minio=minio_sd.name,  # TODO 's3.ca-central-1.amazonaws.com:443',
        minio_access_key='UFSEHRCFU4ACUEWHCHWU',  # TODO s3_access_key.id,
        minio_secret_key='HICSHuhIIUhiuhMIUHIUhGFfUHugy6fGJuyyfiGY',  # TODO s3_access_key.secret
    ).apply(lambda args: [
        { "name": "KRAKEN_REDIS_ADDR", "value": "%s.%s" % (args['redis'], args['domain'])  },
        { "name": "KRAKEN_DB_URL", "value": "postgresql://kraken:kk123kk4321@%s/kraken" % args['pgsql']  },
        { "name": "KRAKEN_CLICKHOUSE_PORT", "value": args['ch_proxy_port']  },
        { "name": "KRAKEN_CLICKHOUSE_ADDR", "value": "%s.%s:%s" % (args['ch_proxy_addr'], args['domain'], args['ch_proxy_port'])  },
        { "name": "KRAKEN_CLICKHOUSE_URL", "value": "http://%s.%s:%s/" % (args['ch_addr'], args['domain'], args['ch_port'])  },
        { "name": "KRAKEN_SERVER_PORT", "value": "6363"  },
        { "name": "KRAKEN_SERVER_ADDR", "value": "server:6363"  },
        { "name": "KRAKEN_PLANNER_URL", "value": "http://%s.%s:7997/" % (args['planner'], args['domain'])  },
        { "name": "KRAKEN_MINIO_ADDR", "value": '%s.%s:9999' % (args['minio'], args['domain'])  },
        { "name": "MINIO_ACCESS_KEY", "value": args['minio_access_key']  },
        { "name": "MINIO_SECRET_KEY", "value": args['minio_secret_key']  },
    ])

    kk_server_sd = kk_service(cluster,
                              role,
                              prv_dns_ns,
                              default_vpc_subnets,
                              secgrp,
                              lg,
                              'kk-server',
                              kk_image('kkserver', kk_ver),
                              2,
                              6363,
                              env=kk_srv_env)

    ####### KK AGENT 1

    kk_agent_env = pulumi.Output.all(
        domain=prv_dns_ns.name,
        ch_proxy_port="9001",                # clickhouse proxy port
        ch_proxy_addr=clickhouse_proxy_sd.name,   # clickhouse proxy addr
        server=kk_server_sd.name,
    ).apply(lambda args: [
        { "name": "KRAKEN_CLICKHOUSE_PORT", "value": args['ch_proxy_port']  },
        { "name": "KRAKEN_CLICKHOUSE_ADDR", "value": "%s.%s:%s" % (args['ch_proxy_addr'], args['domain'], args['ch_proxy_port'])  },
        { "name": "KRAKEN_SERVER_ADDR", "value": "%s.%s:6363" % (args['server'], args['domain'])  },
        { "name": "KRAKEN_AGENT_BUILTIN", "value": "1"  },
    ])

    kk_service(cluster,
               role,
               prv_dns_ns,
               default_vpc_subnets,
               secgrp,
               lg,
               'kk-agent',
               kk_image('kkagent', kk_ver),
               1,
               1234,  # not used
               env=kk_agent_env)

    ####### KK UI

    kk_ui_env = pulumi.Output.all(
        domain=prv_dns_ns.name,
        server=kk_server_sd.name
    ).apply(lambda args: [
        { "name": "KRAKEN_SERVER_ADDR", "value": "%s.%s:6363" % (args['server'], args['domain']) },
    ])

    kk_service(cluster,
               role,
               prv_dns_ns,
               default_vpc_subnets,
               secgrp,
               lg,
               'kk-ui',
               kk_image('kkui', kk_ver),
               1,
               80,
               env=kk_ui_env,
               web_listener=wl,
               target_group=atg)

    export('Kraken Server Address', alb.dns_name.apply(lambda dns_name: '%s' % dns_name))
    export('ClickHouse Proxy Address', pulumi.Output.all(domain=prv_dns_ns.name,
                                                         ch_addr=clickhouse_proxy_sd.name
                                                         ).apply(lambda args: '%s.%s:9001' % (args['ch_addr'], args['domain'])))

main()
