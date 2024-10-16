from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service as ChromeService

# service = ChromeService(executable_path='/Users/solar/Downloads/chrome-mac-x64/Google\\ Chrome\\ for\\ Testing.app/')
driver = webdriver.Chrome()

options = webdriver.ChromeOptions()
options.add_argument("--headless")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--window-size=1920,1080")

data = []

for page_number in range(1, 2):  # Assuming you want to scrape pages 3 to 4
    print(f"Scraping page {page_number}...")

    url = (f'https://zakupki.gov.ru/epz/order/extendedsearch/results.html?searchString=%D0%B1%D0%BB%D0%BE%D0%BA%D0%B8%D1%80%D0%B0%D1%82%D0%BE%D1%80+%D1%83%D1%81%D1%82%D1%80%D0%BE%D0%B9%D1%81%D1%82%D0%B2&morphology=on&search-filter=%D0%94%D0%B0%D1%82%D0%B5+%D1%80%D0%B0%D0%B7%D0%BC%D0%B5%D1%89%D0%B5%D0%BD%D0%B8%D1%8F&pageNumber=1&sortDirection=false&recordsPerPage=_50&showLotsInfoHidden=false&sortBy=UPDATE_DATE&fz44=on&fz223=on&af=on&ca=on&pc=on&currencyIdGeneral=-1&publishDateFrom=01.09.2023')

    driver.get(url)

    # Step 3: Wait for the results to load
    wait = WebDriverWait(driver, 20)
    results = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, '.search-registry-entry-block')))

    print(f"Found {len(results)} results on page {page_number}.")

    # Step 4: Extract the desired data
    for i, result in enumerate(results):
        try:
            print(f"Processing result {i + 1} on page {page_number}...")
            procurement_link = result.find_element(By.CSS_SELECTOR,
                                                   '.registry-entry__header-mid__number a').get_attribute('href')

            initial_price = result.find_element(By.CSS_SELECTOR, '.price-block__value').text.strip().replace('\xa0',
                                                                                                             ' ')
            driver.execute_script("window.open(arguments[0]);", procurement_link)
            driver.switch_to.window(driver.window_handles[1])

            customer = ""
            lot_info = ""
            posted_date = ""

            try:
                wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, '.registry-entry__body-block')))
                body_blocks = driver.find_elements(By.CSS_SELECTOR, '.registry-entry__body-block')

                for block in body_blocks:
                    title_element = block.find_element(By.CSS_SELECTOR, '.registry-entry__body-title').text.strip()

                    if title_element == "Заказчик" or title_element == "Организация, осуществляющая размещение":
                        customer = block.find_element(By.CSS_SELECTOR, '.registry-entry__body-value').text.strip()
                    elif title_element == "Объект закупки":
                        lot_info = block.find_element(By.CSS_SELECTOR, '.registry-entry__body-value').text.strip()

                    if customer and lot_info:
                        break  # Exit the loop once the relevant information is found

                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '.data-block')))
                data_blocks = driver.find_elements(By.CSS_SELECTOR, '.data-block .col-6')

                for block in data_blocks:
                    title_element = block.find_element(By.CSS_SELECTOR, '.data-block__title').text.strip()

                    if title_element == "Размещено":
                        posted_date = block.find_element(By.CSS_SELECTOR, '.data-block__value').text.strip()
                        break  # Exit the loop once the relevant information is found

            except Exception as e:
                print(f"Failed to extract information from the first structure: {e}")

                # If any value is still missing, try the second block
            if not customer or not lot_info or not posted_date:
                try:
                    wait.until(EC.presence_of_all_elements_located(
                        (By.CSS_SELECTOR, '.cardMainInfo__section, .date .row .cardMainInfo__section')))
                    elements = driver.find_elements(By.CSS_SELECTOR,
                                                    '.cardMainInfo__section, .date .row .cardMainInfo__section')

                    for element in elements:
                        title = element.find_element(By.CSS_SELECTOR, '.cardMainInfo__title').text.strip()

                        if title == "Объект закупки":
                            lot_info = element.find_element(By.CSS_SELECTOR, '.cardMainInfo__content').text.strip()
                        elif title == "Заказчик" or title == "Организация, осуществляющая размещение":
                            customer = element.find_element(By.CSS_SELECTOR, '.cardMainInfo__content a').text.strip()
                        elif title == "Размещено":
                            posted_date = element.find_element(By.CSS_SELECTOR, '.cardMainInfo__content').text.strip()

                        if lot_info and customer and posted_date:
                            break  # Exit the loop once the relevant information is found

                except Exception as e:
                    print(f"Failed to extract information from the second structure: {e}")

                # Output the extracted values
            # print(f"Объект закупки: {lot_info}")
            # print(f"Заказчик: {customer}")
            # print(f"Размещено: {posted_date}")

            # Add extracted data to the list
            data.append({
                'Ссылка': procurement_link,
                'Закупка': lot_info,
                'Заказчик': customer,
                'Цена': initial_price,
                'Дата': posted_date
            })

            # Close the new tab and switch back to the original tab
            driver.close()
            driver.switch_to.window(driver.window_handles[0])
        except Exception as e:
            print(f"An error occurred on page {page_number}, result {i + 1}: {e}")
            continue

# Close the WebDriver
driver.quit()

# Step 5: Convert the data to a pandas DataFrame
df = pd.DataFrame(data)

# Step 6: Save the DataFrame to a CSV file
df.to_csv('zakupki.csv', index=False)

print("Data has been saved to csv")
