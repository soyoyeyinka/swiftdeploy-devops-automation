pid /tmp/nginx.pid;

events {}

http {
    log_format swiftdeploy '$time_iso8601 | $status | $request_time s | $upstream_addr | $request';

    access_log /dev/stdout swiftdeploy;
    error_log /dev/stderr warn;

    client_body_temp_path /tmp/client_temp;
    proxy_temp_path /tmp/proxy_temp;
    fastcgi_temp_path /tmp/fastcgi_temp;
    uwsgi_temp_path /tmp/uwsgi_temp;
    scgi_temp_path /tmp/scgi_temp;

    upstream swiftdeploy_upstream {
        server __SERVICE_NAME__:__APP_PORT__;
    }

    server {
        listen __NGINX_PORT__;

        add_header X-Deployed-By "swiftdeploy" always;

        proxy_connect_timeout __PROXY_TIMEOUT__s;
        proxy_send_timeout __PROXY_TIMEOUT__s;
        proxy_read_timeout __PROXY_TIMEOUT__s;

        location / {
            proxy_pass http://swiftdeploy_upstream;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_pass_header X-Mode;
        }

        error_page 502 = @error502;
        error_page 503 = @error503;
        error_page 504 = @error504;

        location @error502 {
            default_type application/json;
            return 502 '{"error":"bad_gateway","code":"502","service":"__SERVICE_NAME__","contact":"__CONTACT__"}';
        }

        location @error503 {
            default_type application/json;
            return 503 '{"error":"service_unavailable","code":"503","service":"__SERVICE_NAME__","contact":"__CONTACT__"}';
        }

        location @error504 {
            default_type application/json;
            return 504 '{"error":"gateway_timeout","code":"504","service":"__SERVICE_NAME__","contact":"__CONTACT__"}';
        }
    }
}
