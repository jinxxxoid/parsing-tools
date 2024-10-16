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

    url = (f'https://zakupki.gov.ru/epz/contract/search/results.html?searchString=%D1%81%D0%B8%D0%B3%D0%BD%D0%B0%D0%BB+%D0%B1%D0%B5%D1%81%D0%BF%D0%B8%D0%BB%D0%BE%D1%82%D0%BD%D1%8B%D0%B9&morphology=on&search-filter=%D0%94%D0%B0%D1%82%D0%B5+%D1%80%D0%B0%D0%B7%D0%BC%D0%B5%D1%89%D0%B5%D0%BD%D0%B8%D1%8F&fz44=on&contractStageList_0=on&contractStageList_1=on&contractStageList=0%2C1&budgetLevelsIdNameHidden=%7B%7D&contractDateFrom=01.09.2023&sortBy=UPDATE_DATE&pageNumber=1&sortDirection=false&recordsPerPage=_50&showLotsInfoHidden=false')

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

            try:
                procurement_number = (result.find_element(By.CSS_SELECTOR, ".lots-wrap-content__body__val .col span")
                                      .text.strip())

            except Exception as e:
                print(f"Procurement number not found for result {i + 1} on page {page_number}: {e}")
                procurement_number = "N/A"

            customer = result.find_element(By.CSS_SELECTOR, '.registry-entry__body-href a').text.strip()
            initial_price = result.find_element(By.CSS_SELECTOR, '.price-block__value').text.strip().replace('\xa0',
                                                                                                             ' ')
            posted_date = result.find_element(By.XPATH, ".//div[contains(@class, 'data-block__value') and "
                                                        "preceding-sibling::div[contains(text(), "
                                                        "'Размещен контракт в реестре контрактов')]]").text.strip()

            # Click the link to open in a new tab
            driver.execute_script("window.open(arguments[0]);", procurement_link)
            driver.switch_to.window(driver.window_handles[1])

            # Wait for the new tab to load and extract "section__info" where "section__title" is "Лот"
            lot_info = ""
            try:
                # wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '.sectionMainInfo')))
                sections = driver.find_elements(By.CSS_SELECTOR, '.sectionMainInfo .cardMainInfo__section')
                for section in sections:
                    title_element = section.find_element(By.CSS_SELECTOR, '.cardMainInfo__title').text.strip()
                    if title_element == "Объекты закупки":
                        # Extract the text from the span element within "Объекты закупки"
                        lot_info = section.find_element(By.CSS_SELECTOR,
                                                        '.cardMainInfo__content .text-break').text.strip()
                        break  # Exit the loop once the relevant information is found

            except Exception as e:
                print(f"Failed to extract 'Объекты закупки' info for result {i + 1} on page {page_number}: {e}")

            # Add extracted data to the list
            data.append({
                'Ссылка': procurement_link,
                'Закупка': lot_info,
                'Заказчик': customer,
                'Initial Price': initial_price,
                'Posted Date': posted_date
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
df.to_csv('FZ44.csv', index=False)

print("Data has been saved to csv")
