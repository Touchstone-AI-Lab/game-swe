# Separate verifier image for one Mindustry (game source) repair task.
#
# Harbor builds this file from the task's tests/ directory after the agent
# environment has stopped, so the private suite never enters the agent image.
# The base is the locally built, pinned Mindustry runtime; it is never published.
# The grader suite is compiled and packaged with the trusted harness here, so the
# verifier itself runs with no network.
FROM rhenium-mindustry-verifier:159.7

USER root
COPY suite /tests/suite
RUN bash /opt/rhenium/build-grader.sh /tests/suite /opt/rhenium/grader/rhenium-grader.jar
COPY --chmod=755 test.sh /tests/test.sh
COPY verify.py task.json /tests/
RUN mkdir -p /app/mindustry /logs /work
WORKDIR /app
ENTRYPOINT []
CMD ["sleep", "infinity"]
