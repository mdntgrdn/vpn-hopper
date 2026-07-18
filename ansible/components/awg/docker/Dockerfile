FROM golang:1.25-alpine AS builder

RUN apk add --no-cache git

RUN git clone https://github.com/amnezia-vpn/amneziawg-go.git /src
WORKDIR /src
RUN go build -o /amneziawg-go


FROM alpine:3.19

RUN apk add --no-cache \
    bash \
    iptables \
    ip6tables \
    iproute2 \
    openresolv \
    libcap \
    ca-certificates \
    curl \
    unzip

RUN curl -L -o /tmp/awg-tools.zip \
    https://github.com/amnezia-vpn/amneziawg-tools/releases/latest/download/alpine-3.19-amneziawg-tools.zip \
    && unzip -j /tmp/awg-tools.zip -d /usr/bin \
    && chmod +x /usr/bin/awg /usr/bin/awg-quick \
    && rm /tmp/awg-tools.zip

COPY --from=builder /amneziawg-go /usr/bin/amneziawg-go

RUN ln -sf /usr/bin/awg /usr/bin/wg \
    && ln -sf /usr/bin/awg-quick /usr/bin/wg-quick

CMD ["sh"]
