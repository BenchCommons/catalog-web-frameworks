FROM julia:1.13.4@sha256:be25fa7dfa0374fa9e14f87fd3356b4efd1b765e639a7306d9a1d255912564ce

WORKDIR /app
COPY ./src ./
RUN julia --project -e 'using Pkg; Pkg.instantiate()'

EXPOSE 8080
CMD julia -t 2 --project server.jl