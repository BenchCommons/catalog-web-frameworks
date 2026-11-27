FROM rstudio/plumber:v1.3.0@sha256:e34ec5f792bca95cd815688af083bcf5929efcecc9736f130abcbbcfb28ca58f

RUN apt-get update

RUN apt install postgresql postgresql-contrib -y

RUN R -e "install.packages(c('DBI', 'RPostgres', 'plyr', 'dplyr', 'stringr'))"

ADD ./ /plumber

WORKDIR /plumber

EXPOSE 8080

CMD ["deploy_plumber.R"]
