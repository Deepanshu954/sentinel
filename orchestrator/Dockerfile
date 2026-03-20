# Build stage
FROM maven:3.9.6-eclipse-temurin-21-jammy AS build
WORKDIR /app
COPY pom.xml .
COPY src ./src
# Build the JAR
RUN mvn clean package -DskipTests

# Run stage
FROM eclipse-temurin:21-jre-jammy
RUN groupadd -r sentinel && useradd -r -g sentinel sentinel
WORKDIR /app
COPY --from=build /app/target/*.jar app.jar
RUN chown sentinel:sentinel /app/app.jar
USER sentinel
EXPOSE 8090
CMD ["java", "-jar", "app.jar"]
