FROM golang:1.25-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    ca-certificates \
    curl \
    git \
    make \
    nodejs \
    npm \
    sudo \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --home-dir /home/gentle --shell /bin/bash gentle \
    && usermod --append --groups sudo gentle \
    && printf 'gentle ALL=(ALL) NOPASSWD:ALL\n' > /etc/sudoers.d/gentle \
    && chmod 0440 /etc/sudoers.d/gentle

USER gentle

ENV HOME=/home/gentle \
    GOPATH=/home/gentle/go \
    GOBIN=/home/gentle/go/bin \
    PATH=/home/gentle/go/bin:/usr/local/go/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

WORKDIR /home/gentle

# Official source-based install path from the project README.
RUN go install github.com/gentleman-programming/gentle-ai/cmd/gentle-ai@latest

# Start inside the isolated home filesystem.
CMD ["sh"]
