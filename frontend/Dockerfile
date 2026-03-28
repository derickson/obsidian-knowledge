FROM node:22-slim AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

ARG API_PREFIX=/obsidian-knowledge
ENV API_PREFIX=${API_PREFIX}

RUN npm run build

FROM node:22-slim

WORKDIR /app

RUN npm install -g serve

COPY --from=build /app/dist ./dist

ARG API_PREFIX=/obsidian-knowledge
ENV API_PREFIX=${API_PREFIX}

EXPOSE 8104
CMD ["sh", "-c", "serve -s dist -l 8104 --single"]
