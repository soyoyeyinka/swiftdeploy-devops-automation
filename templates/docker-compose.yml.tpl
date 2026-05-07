services:
  app:
    image: __SERVICE_IMAGE__
    container_name: __SERVICE_NAME__
    restart: __RESTART_POLICY__
    environment:
      MODE: "__MODE__"
      APP_VERSION: "__APP_VERSION__"
      APP_PORT: "__APP_PORT__"
    expose:
      - "__APP_PORT__"
    networks:
      - swiftdeploy-network
    healthcheck:
      test: ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://localhost:__APP_PORT__/healthz', timeout=3).read()\""]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 5s
    cap_drop:
      - ALL
    security_opt:
      - no-new-privileges:true

  nginx:
    image: __NGINX_IMAGE__
    container_name: swiftdeploy-nginx
    restart: __RESTART_POLICY__
    user: "101:101"
    ports:
      - "__NGINX_PORT__:__NGINX_PORT__"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - swiftdeploy-logs:/tmp/swiftdeploy-logs
    depends_on:
      app:
        condition: service_healthy
    networks:
      - swiftdeploy-network
    cap_drop:
      - ALL
    security_opt:
      - no-new-privileges:true

networks:
  swiftdeploy-network:
    name: __NETWORK_NAME__
    driver: __NETWORK_DRIVER__

volumes:
  swiftdeploy-logs:
    name: __LOG_VOLUME__
