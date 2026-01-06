#env environment
docker compose up --build

#prod
docker-compose -f docker-compose.yaml -f docker-compose.prod.yaml up --build -d

Environment	Frontend API URL	Note
Development	http://localhost:5000/api/hello	Browser talks directly to the Flask container
Development	http://localhost:5173/	        Browser talks directly to the VueJs container which proxies to http://localhost:5000/api
Production	/api/ (or /api/your-endpoint)	Browser talks to Nginx, which proxies to http://backend:8000