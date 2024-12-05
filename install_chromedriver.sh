#!/bin/bash

# Chrome 버전 확인
CHROME_VERSION=$(google-chrome --version | awk '{print $3}')
echo "Detected Chrome version: $CHROME_VERSION"

# ChromeDriver URL
CHROMEDRIVER_URL="https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/${CHROME_VERSION}/linux64/chromedriver-linux64.zip"

# 패키지 설치
sudo apt-get install zip

# ChromeDriver 다운로드 및 설치
wget -O chromedriver_linux64.zip $CHROMEDRIVER_URL
unzip -o chromedriver_linux64.zip
sudo mv -f chromedriver-linux64/chromedriver /usr/local/bin/chromedriver
sudo chown root:root /usr/local/bin/chromedriver
sudo chmod +x /usr/local/bin/chromedriver

# 정리
rm -rf chromedriver_linux64.zip chromedriver-linux64

echo "ChromeDriver $CHROME_VERSION has been installed successfully."
chromedriver --version

# 참고 (https://makepluscode.tistory.com/entry/WSL2%EC%97%90%EC%84%9C-Selenium-%EC%82%AC%EC%9A%A9%ED%95%98%EA%B8%B0)