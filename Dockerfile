FROM ubuntu:22.04

# Prevent interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

# Install dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    build-essential \
    libssl-dev \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Luvit
WORKDIR /tmp
RUN curl -L https://github.com/luvit/lit/raw/master/get-lit.sh -o get-lit.sh && \
    chmod +x get-lit.sh && \
    ./get-lit.sh && \
    mv luvi /usr/local/bin/ && \
    mv luvit /usr/local/bin/ && \
    mv lit /usr/local/bin/ && \
    rm get-lit.sh

# Set working directory
WORKDIR /app

# Copy everything
COPY . .

# Install Lua dependencies
RUN lit install

# Verify bot.lua exists
RUN ls -la /app/ && test -f /app/bot.lua || (echo "ERROR: bot.lua not found!" && exit 1)

# Start the bot
CMD ["luvit", "bot.lua"]