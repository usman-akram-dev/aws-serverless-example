from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    aws_rds as rds,
    aws_secretsmanager as secretsmanager,
    Duration, 
    RemovalPolicy,
    aws_lambda as lambda_,
    aws_apigateway as apigateway,
    aws_iam as iam,
    
)
from constructs import Construct
from datetime import datetime
from os import path
from aws_cdk.custom_resources import (
    AwsCustomResource,
    AwsCustomResourcePolicy,
    PhysicalResourceId,
    AwsSdkCall
)

class ServerlessExampleStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # provision a VPC
        self.vpc = ec2.Vpc(self, 'ECommerceServerlessVPC',
                           subnet_configuration=[
                                 ec2.SubnetConfiguration(name='isoltated', subnet_type=ec2.SubnetType.PRIVATE_ISOLATED),
                                 ec2.SubnetConfiguration(name='public', subnet_type=ec2.SubnetType.PUBLIC),
                                 ec2.SubnetConfiguration(name='private', subnet_type=ec2.SubnetType.PRIVATE_WITH_NAT),
                           ]
                           )
        
        db_user_name = "db_user"
        self.rds_secret = secretsmanager.Secret(self, 'ProductRDSProxySecret',
                              secret_name=construct_id + '-rds-credentials',
                              generate_secret_string=secretsmanager.SecretStringGenerator(
                                    secret_string_template='{{"username": "{}"}}'.format(db_user_name),
                                    generate_string_key='password',
                                    exclude_punctuation=True,
                                    include_space=False,
                              ))
        
        # lamda security group
        self.lambda_sg = ec2.SecurityGroup(self, 'LambdaSG', vpc=self.vpc)
        # self.lambda_sg.add_egress_rule(ec2.Peer.any_ipv4(), ec2.Port.all_traffic(), 'allow lambda to connect to rds proxy')

        # rds proxy security group
        self.rds_proxy_sg = ec2.SecurityGroup(self, 'RDSProxySG', vpc=self.vpc)
        self.rds_proxy_sg.add_ingress_rule(self.lambda_sg, ec2.Port.tcp(3306), 'allow lambda to connect to rds proxy')

        # rds security group 
        self.rds_sg = ec2.SecurityGroup(self, 'RDSSG', vpc=self.vpc)
        self.rds_sg.add_ingress_rule(self.rds_proxy_sg, ec2.Port.tcp(3306), 'allow rds proxy to connect to rds')

        rds_credentials = rds.Credentials.from_secret(self.rds_secret)

        #create rds cluster
        self.rds = rds.DatabaseCluster(self, 'ProductDBCluster',
                            instance_props=rds.InstanceProps(vpc=self.vpc, 
                                                             vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_ISOLATED),
                                                             instance_type=ec2.InstanceType.of(ec2.InstanceClass.T3, ec2.InstanceSize.MEDIUM),
                                                             security_groups=[self.rds_sg],
                            ),
                            cluster_identifier="ProductDBCluster",
                            engine=rds.DatabaseClusterEngine.aurora_mysql(version=rds.AuroraMysqlEngineVersion.VER_3_02_1),
                            instances=1,
                            backup=rds.BackupProps(retention=Duration.days(1)),
                            removal_policy=RemovalPolicy.DESTROY,
                            credentials=rds_credentials,
                            default_database_name="product_db",
        )



        #create rds proxy
        self.rds_proxy: rds.DatabaseProxy = self.rds.add_proxy('ProductDBProxy', secrets=[self.rds_secret], 
                           vpc=self.vpc, 
                            security_groups=[self.rds_proxy_sg],
                            debug_logging=True,
                            iam_auth=True)
        # self.rds_proxy.node.add_dependency(self.rds)
        
        # lambda function for inserting a product
        lambda_layer = lambda_.LayerVersion(self, "boto3pymsqllayer",
                            removal_policy=RemovalPolicy.RETAIN,
                            code=lambda_.Code.from_asset("./code/lambda/layers/layers.zip"),
                            compatible_runtimes=[lambda_.Runtime.PYTHON_3_8],
                            compatible_architectures=[lambda_.Architecture.ARM_64],
                            description="boto3 and pymysql layer for lambda",
                            layer_version_name="boto3pymsqllayer"
                             )


        create_product_lambda = lambda_.Function(self, construct_id + 'CreateProductLambda',
                            memory_size=1024,
                            timeout=Duration.seconds(30),
                            runtime=lambda_.Runtime.PYTHON_3_8,
                            handler='fetch_products.lambda_handler',
                            code=lambda_.Code.from_asset("./code/lambda/product_api"),
                            vpc=self.vpc,
                            layers=[lambda_layer],
                            architecture=lambda_.Architecture.ARM_64,
                            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_ISOLATED),
                            security_groups=[self.lambda_sg],
                            environment={ "DB_LOCATION": self.rds_proxy.endpoint,
                                            "DB_USER": db_user_name,
                                            "DB_NAME": "product_db"}
                            )

        self.rds_proxy.grant_connect(create_product_lambda, db_user_name)
        # create_product_lambda.node.add_dependency(self.rds_proxy)

        api_gateway = apigateway.RestApi(self, "ProductAPI")
        product_resource = api_gateway.root.add_resource("product")
        product_resource.add_method("POST", apigateway.LambdaIntegration(create_product_lambda))


        # # populate the database lambda function
        create_database_lambda = lambda_.Function(self, construct_id + 'CreateProductDatabaseLambda',
                            memory_size=1024,
                            timeout=Duration.seconds(240),
                            runtime=lambda_.Runtime.PYTHON_3_8,
                            handler='create_db.lambda_handler',
                            code=lambda_.Code.from_asset("./code/lambda/db-init"),
                            vpc=self.vpc,
                            layers=[lambda_layer],
                            architecture=lambda_.Architecture.ARM_64,
                            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_ISOLATED),
                            security_groups=[self.lambda_sg],
                            environment={ "DB_LOCATION": self.rds_proxy.endpoint,
                                            "DB_USER": db_user_name,
                                            "DB_NAME": "product_db"}
                            )
        
        self.rds_proxy.grant_connect(create_database_lambda, db_user_name)

        ## a custom resource to listen to the CDK events and invoke a function to create database table and insert rows in it
        database_lambda_triger = AwsCustomResource(self, 'CreateDatabaseTrigger',
                          policy=AwsCustomResourcePolicy.from_statements([ 
                                                    iam.PolicyStatement( effect=iam.Effect.ALLOW, 
                                                                        resources=[create_database_lambda.function_arn],
                                                                         actions=['lambda:InvokeFunction'])]),
                          timeout=Duration.minutes(15),
                          on_create=AwsSdkCall(service='Lambda', 
                                               parameters={'FunctionName': create_database_lambda.function_name, 
                                                              'InvocationType': 'Event'},
                                               action='invoke', 
                                               physical_resource_id=PhysicalResourceId.of(str(datetime.now) + "_dynamic"))
        )

        database_lambda_triger.node.add_dependency(self.rds_proxy, create_database_lambda)                                                                
                                         






