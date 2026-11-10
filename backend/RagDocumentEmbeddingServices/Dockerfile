FROM python:3.12-slim@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b AS ocr-build

RUN apt-get update && apt-get install -y --no-install-recommends \
    cmake ninja-build g++ pkg-config libleptonica-dev tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*
ADD --checksum=sha256:a8dbf8b8c8ee427ff6ad1d99116502feaf59440af1adb893caf60a6576826cf4 \
    https://codeload.github.com/tesseract-ocr/tesseract/tar.gz/refs/tags/5.5.4 /tmp/tesseract.tar.gz
RUN mkdir /source && tar -xzf /tmp/tesseract.tar.gz -C /source --strip-components=1 \
    && cmake -G Ninja -S /source -B /build -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/opt/tesseract \
       -DBUILD_SHARED_LIBS=ON -DBUILD_TRAINING_TOOLS=OFF -DBUILD_TESTS=OFF \
       -DDISABLE_ARCHIVE=ON -DDISABLE_CURL=ON -DGRAPHICS_DISABLED=ON -DENABLE_NATIVE=OFF \
    && cmake --build /build --parallel 4 && cmake --install /build \
    && mkdir -p /opt/tesseract/share/tessdata /opt/tesseract/share/licenses \
    && cp /usr/share/tesseract-ocr/5/tessdata/eng.traineddata /opt/tesseract/share/tessdata/ \
    && cp /source/LICENSE /opt/tesseract/share/licenses/tesseract-LICENSE \
    && cp /usr/share/doc/tesseract-ocr-eng/copyright /opt/tesseract/share/licenses/tessdata-eng-copyright

FROM python:3.12-slim@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b AS base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV HF_HOME=/tmp/embedding-model-cache
ENV PATH=/opt/tesseract/bin:$PATH
ENV LD_LIBRARY_PATH=/opt/tesseract/lib
ENV TESSDATA_PREFIX=/opt/tesseract/share/tessdata

WORKDIR /app

RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && apt-get install -y --no-install-recommends libleptonica6 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10004 embedding \
    && useradd --uid 10004 --gid embedding --no-create-home embedding \
    && install -d -o embedding -g embedding /app/documents

RUN pip install --no-cache-dir torch==2.15.0 --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
RUN pip install --no-cache-dir pip==26.3 setuptools==84.2.1 \
    && pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY --from=ocr-build /opt/tesseract /opt/tesseract
# Image OCR does not support remote URLs or archives. Do not ship their XML parser.
RUN tesseract --version \
    && for package in libxml2 libarchive13t64 libcurl4t64; do \
         if dpkg-query -W -f='${db:Status-Status}' "$package" 2>/dev/null | grep -qx installed; then \
           echo "Unexpected installed native dependency: $package" >&2; exit 1; fi; done \
    && ! ldd /opt/tesseract/bin/tesseract | grep -E 'libxml2|libarchive|libcurl'

FROM base AS test

COPY requirements-test.txt .
RUN pip install --no-cache-dir -r requirements-test.txt
COPY tests ./tests
USER 10004:10004
CMD ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests"]

FROM base AS runtime

RUN python -m pip check && python -m pip uninstall -y pip && rm -rf /usr/local/lib/python3.12/ensurepip

USER 10004:10004
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
