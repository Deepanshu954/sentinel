FROM eclipse-temurin:21-jre-jammy

RUN groupadd -r sentinel && useradd -r -g sentinel sentinel

WORKDIR /app

COPY target/*.jar app.jar

RUN chown sentinel:sentinel /app/app.jar

USER sentinel

EXPOSE 8090

CMD ["java", "-jar", "app.jar"]
