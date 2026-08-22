FROM python:3.13-slim
RUN useradd --system --uid 10001 --create-home astra
WORKDIR /opt/astravcs
COPY reference ./reference
COPY tools/serve.py ./serve.py
RUN mkdir -p /var/lib/astravcs && chown -R astra:astra /var/lib/astravcs /opt/astravcs
USER 10001
ENV PYTHONPATH=/opt/astravcs/reference PYTHONUNBUFFERED=1
EXPOSE 8080
VOLUME ["/var/lib/astravcs"]
ENTRYPOINT ["python","/opt/astravcs/serve.py","--root","/var/lib/astravcs","--host","0.0.0.0","--port","8080"]
