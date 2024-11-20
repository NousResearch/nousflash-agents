FROM node:23.1.0

RUN npm install -g pnpm@9.12.3

WORKDIR /app

COPY . .
RUN pnpm clean
RUN pnpm i
RUN pnpm build

EXPOSE 3007

CMD ["pnpm", "dev"]