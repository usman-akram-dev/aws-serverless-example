A serverless stack consists of API Gateway, Lambda, RDS Proxy and RDS Aurora

1. **API Gateway (AGW)**: The API Gateway serves as the entry point for incoming requests to the serverless application. It handles request routing, authentication, and authorization, directing traffic to the appropriate AWS Lambda function.

2. **AWS Lambda**: AWS Lambda is a serverless compute service that runs code in response to events. In this stack, Lambda functions are responsible for executing the business logic of the application. They interact with other services like RDS Proxy and RDS Aurora to perform data operations.

3. **Amazon RDS Proxy (RDS Proxy)**: The RDS Proxy acts as an intermediary between the Lambda functions and the Amazon RDS Aurora database. It helps manage and optimize database connections, improving performance, and reducing latency for serverless applications that require database access.

4. **Amazon RDS Aurora (RDS Aurora)**: RDS Aurora is the fully managed relational database service that stores and manages application data. It provides high availability, durability, and scalability for the serverless application's data storage needs.

In this serverless architecture, the API Gateway forwards requests to the appropriate Lambda functions. These Lambda functions then interact with the RDS Proxy, which, in turn, optimizes and manages connections to the RDS Aurora database. This serverless stack offers a scalable, cost-effective, and low-maintenance solution for running applications without the need to manage traditional servers.

![LambdaArch](https://github.com/usman-akram-dev/aws-serverless-example/assets/7351877/8d96ed71-50ee-42a9-bde2-5efbc5a2b159)
