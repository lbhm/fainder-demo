FROM node:22-slim

WORKDIR /app

COPY . .
RUN npm install --omit=dev
RUN npm run build

EXPOSE 3000

CMD ["npm", "run", "dev"]
