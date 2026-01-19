FROM ubuntu:22.04

# Install dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    build-essential \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Luvit
RUN curl -L https://github.com/luvit/lit/raw/master/get-lit.sh | sh
RUN mv luvi /usr/local/bin/
RUN mv luvit /usr/local/bin/
RUN mv lit /usr/local/bin/

# Set working directory
WORKDIR /app

# Copy project files
COPY . .

# Install Lua dependencies
RUN lit install

# Start the bot
CMD ["luvit", "bot.lua"]