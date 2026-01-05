#env environment
docker-compose -f docker-compose.yaml -f docker-compose.dev.yaml up --build

#prod
docker-compose -f docker-compose.yaml -f docker-compose.prod.yaml up --build -d

Environment	Frontend API URL	Note
Development	http://localhost:5000/	Browser talks directly to the Flask container
Production	/api/ (or /api/your-endpoint)	Browser talks to Nginx, which proxies to http://backend:8000