# Deploy to Oracle Cloud Free Tier

Run both frontend and backend in a single container behind nginx.

## 1. Create Oracle Cloud Free Tier Instance

1. Go to [cloud.oracle.com](https://cloud.oracle.com)
2. Navigate to **Compute > Instances > Create Instance**
3. Choose **Ampere A1** (ARM) shape — **Always Free eligible**
   - OCPUs: `2`
   - Memory: `24 GB` (use what you need, up to 4 OCPUs)
   - Image: **Oracle Linux 8** or **Ubuntu 22.04**
4. Enable SSH and add your public key (or generate the key in the UI)
5. Note the **Public IP** after creation

## 2. Open Port 80 (and optionally 443)

In your Compartment > **Virtual Cloud Networks > your VCN > Security List**, add an ingress rule for TCP port 80. Also open port 22 (SSH).

## 3. SSH Into the Server

```bash
ssh -i ~/.ssh/your_key opc@<SERVER_PUBLIC_IP>
```

## 4. Install Docker + Docker Compose

```bash
# Install Docker
sudo dnf install -y docker-engine  # Oracle Linux
# OR
sudo apt update && sudo apt install -y docker.io  # Ubuntu

# Start & enable Docker
sudo systemctl start docker
sudo systemctl enable docker

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-aarch64" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Add your user to docker group (optional)
sudo usermod -aG docker $USER
```

## 5. Deploy the App

```bash
# Clone your repo
git clone https://github.com/koriaryan1432/terraform-ai-assistant.git
cd terraform-ai-assistant/deploy

# Create .env with your actual API key
nano .env
# Add: GROQ_API_KEY=gsk_your_actual_key
```

Or use the existing project root `.env`:

```bash
cp ../.env .
```

Then start:

```bash
# Copy env file to the deploy directory
cp .env ./.env

# Build and start
docker-compose -f docker-compose.deploy.yml up --build -d

# Check logs
docker-compose -f docker-compose.deploy.yml logs -f
```

## 6. Verify

```bash
curl http://localhost/health
```

Open `http://<your-server-ip>` in a browser. The app should be running.

## 7. (Optional) Add a Domain + SSL

If you want HTTPS with Let's Encrypt:

```bash
# Point a DNS A record to your server IP
# Install certbot
sudo dnf install -y certbot  # Oracle Linux

# Get a certificate
sudo certbot certonly --standalone -d your-domain.com

# Update docker-compose to mount certificates and use HTTPS
# See certbot comments in docker-compose.deploy.yml
```

## 8. Update the App

```bash
cd ~/terraform-ai-assistant
git pull
cd deploy
docker-compose -f docker-compose.deploy.yml up --build -d
```

## Important Notes

- The free tier instance gives you **24 GB RAM** and **4 ARM cores** — more than enough for this app
- Always free = **no expiration** as long as you have an active Oracle Cloud account
- The app uses ~50-100MB RAM and <1 CPU core under normal usage
- If you're not using a domain, anyone with your IP can access — add HTTP auth or restrict the VCN security list for private testing
