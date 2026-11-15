# Deploy to AWS (EC2 + Docker Compose)

This is the simplest production-like setup: one small EC2 server runs both the API and the web app with Docker Compose. Uploaded documents are stored on a Docker volume, so they survive restarts and redeploys.

Expected cost: a `t3.small` costs roughly $15/month on demand (a `t3.micro` can work for a light demo and may be covered by the AWS free tier). Claude API usage is billed separately by Anthropic.

## 1. Set a billing alarm first

AWS Console → Billing → Budgets → Create budget → "Monthly cost budget" → $10 → your email. This protects you from surprise bills.

## 2. Launch the server

1. EC2 → Launch instance.
2. Name: `rag-chatbot`. Image: **Ubuntu Server 24.04 LTS**. Type: **t3.small**.
3. Key pair: create one and download the `.pem` file.
4. Network settings → allow **SSH (22) from My IP**, and add rules for **TCP 3000** and **TCP 8000** from anywhere (0.0.0.0/0).
5. Storage: 20 GB. Launch.
6. Optional but recommended: Elastic IPs → Allocate → Associate with the instance, so the IP never changes.

## 3. Install Docker

```bash
ssh -i rag-chatbot.pem ubuntu@<SERVER_IP>
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker ubuntu && exit
```

Log in again so the group change applies.

## 4. Get the code and configure

```bash
ssh -i rag-chatbot.pem ubuntu@<SERVER_IP>
git clone https://github.com/<your-username>/rag-document-chatbot.git
cd rag-document-chatbot
cp backend/.env.example backend/.env
nano backend/.env          # paste your ANTHROPIC_API_KEY
```

## 5. Start it

```bash
export PUBLIC_API_URL=http://<SERVER_IP>:8000
export PUBLIC_WEB_URL=http://<SERVER_IP>:3000
docker compose up -d --build
```

Open `http://<SERVER_IP>:3000`. The first build takes a few minutes because it downloads the embedding model.

## 6. Update after a code change

```bash
cd rag-document-chatbot && git pull
docker compose up -d --build
```

## Next steps for a real client

- **HTTPS and a domain:** point a domain at the Elastic IP and put [Caddy](https://caddyserver.com/docs/quick-starts/reverse-proxy) in front (`web` on 443, `api` on a subdomain), then close ports 3000 and 8000 to the public.
- **Protect the API:** add an API key or login before sharing the link widely, because anyone with the URL can spend your Claude credits.
- **Scale up:** move the vector store to a managed service (for example Amazon OpenSearch or PostgreSQL with pgvector on RDS) and run the API on ECS Fargate or App Runner.
