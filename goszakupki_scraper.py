from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service as ChromeService
import pandas as pd

# Step 1: Set up the Selenium WebDriver using WebDriver Manager with headless mode
service = ChromeService(executable_path=ChromeDriverManager().install())
options = webdriver.ChromeOptions()
options.add_argument("--headless")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--window-size=1920,1080")
driver = webdriver.Chrome(service=service, options=options)

# Initialize the data list
data = []

# Step 2: Loop through the pages
for page_number in range(1, 4):  # Assuming you want to scrape pages 3 to 4
    print(f"Scraping page {page_number}...")

    # Construct the URL with the appropriate page number
    url = (f'https://zakupki.gov.ru/epz/contract/search/results.html?searchString=%D0%B7%D0%B0%D1%89%D0%B8%D1%82%D0%BD'
           f'%D1%8B%D0%B5+%D1%81%D0%BE%D0%BE%D1%80%D1%83%D0%B6%D0%B5%D0%BD%D0%B8%D1%8F+%D0%B3%D1%80%D0%B0%D0%B6%D0%B4'
           f'%D0%B0%D0%BD%D1%81%D0%BA%D0%BE%D0%B9+%D0%BE%D0%B1%D0%BE%D1%80%D0%BE%D0%BD%D1%8B&morphology=on&search'
           f'-filter=%D0%94%D0%B0%D1%82%D0%B5+%D1%80%D0%B0%D0%B7%D0%BC%D0%B5%D1%89%D0%B5%D0%BD%D0%B8%D1%8F&fz44=on'
           f'&contractStageList_0=on&contractStageList_1=on&contractStageList=0%2C1&budgetLevelsIdNameHidden=%7B%7D'
           f'&publishDateFrom=01.01.2019&publishDateTo=01.01.2020&sortBy=UPDATE_DATE&pageNumber='
           f'{page_number}&sortDirection=false&recordsPerPage=_50&showLotsInfoHidden=false')

    driver.get(url)

    # Step 3: Wait for the results to load
    wait = WebDriverWait(driver, 20)
    results = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, '.search-registry-entry-block')))

    print(f"Found {len(results)} results on page {page_number}.")

    # Step 4: Extract the desired data
    for i, result in enumerate(results):
        try:
            print(f"Processing result {i + 1} on page {page_number}...")
            procurement_link = result.find_element(By.CSS_SELECTOR, '.registry-entry__header-mid__number a').get_attribute('href')

            try:
                procurement_number = result.find_element(By.CSS_SELECTOR, '.registry-entry__body-value').text.strip()
            except Exception as e:
                print(f"Procurement number not found for result {i + 1} on page {page_number}: {e}")
                procurement_number = "N/A"

            customer = result.find_element(By.CSS_SELECTOR, '.registry-entry__body-href a').text.strip()
            initial_price = result.find_element(By.CSS_SELECTOR, '.price-block__value').text.strip().replace('\xa0', ' ')
            posted_date = result.find_element(By.XPATH, ".//div[contains(@class, 'data-block__value') and "
                                                        "preceding-sibling::div[contains(text(), "
                                                        "'Размещен контракт в реестре контрактов')]]").text.strip()

            # Click the link to open in a new tab
            driver.execute_script("window.open(arguments[0]);", procurement_link)
            driver.switch_to.window(driver.window_handles[1])

            # Wait for the new tab to load and extract "section__info" where "section__title" is "Лот"
            lot_info = ""
            try:
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '.blockInfo__section')))
                sections = driver.find_elements(By.CSS_SELECTOR, '.blockInfo__section section')
                for section in sections:
                    title = section.find_element(By.CSS_SELECTOR, '.section__title').text.strip()
                    if title == "Предмет контракта":
                        lot_info = section.find_element(By.CSS_SELECTOR, '.section__info').text.strip()
                        break
            except Exception as e:
                print(f"Failed to extract 'Лот' info for result {i + 1} on page {page_number}: {e}")

            # Add extracted data to the list
            data.append({
                'Procurement Link': procurement_link,
                'Procurement Number': procurement_number,
                'Lot Info': lot_info,
                'Customer': customer,
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
df.to_csv('FZ44_2019_detailed.csv', index=False)

print("Data has been saved to csv")
