FROM node:22-slim

WORKDIR /app

COPY . .
RUN npm install
RUN npm run build

EXPOSE 3000
ARG NUXT_MODE=preview

CMD echo ${NUXT_MODE} && npm run $NUXT_MODE
