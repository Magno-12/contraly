## Project Architecture

The `apps` directory serves as a collection of all the individual applications that make up this Django project. Each application is self-contained, with its own set of models, views, serializers, and tests, promoting a clean separation of concerns.

### Applications Structure

Each application in the `apps` directory is a vital component of the django project, carefully designed to emphasize functionality and scalability. The structure of these applications is organized as follows:

- `models/`: A directory containing ORM models that define the database schema and business logic. Each model represents a table in the database and encapsulates the associated data.
- `tests/`: This directory hosts a suite of tests, ensuring all code adheres to our high quality standards and functions as expected.
- `serializers/`: Contains Django Rest Framework serializers for efficient data serialization. These serializers facilitate the transformation of model instances to JSON format and vice versa, for API communication.
- `views/`: A collection of views that manage HTTP requests and responses, employing serializers and models to execute the application's business logic.
- `urls.py`: This file outlines the URL routes for the application, an essential component for REST API design, mapping endpoints to their respective views.
- `admin.py`: Configures the admin interface for the application's models, offering a powerful and customizable tool for administrative tasks.
- `apps.py`: Defines the application's configuration and includes any app-specific settings.

With this modular and organized structure, each application is not only self-contained but also designed to integrate smoothly with the overall system, maintaining a clean and manageable codebase.


- Dependency injection is employed throughout the applications, particularly in user creation, to maintain clean, maintainable, and testable code.

## Requirements to Run the Project

### Clone the Repository

- Clone the repository to your machine:

```python
git clone https://github.com/Magno-12/contraly
```

- Create a virtual environment using the following installation and activation commands:

```python
pip install virtualenv
virtualenv env
```

**On Windows:**
```python
env\Scripts\activate
```

**On macOS and Linux:**
```python
source env/bin/activate
```

- Ensure you have Python 3.x installed on your system. You will also need to install the project's dependencies. You can do this using pip:

```python
pip install -r requirements.txt
```

- Run the Django application:

```python
python manage.py runserver
```
Visit http://127.0.0.1:8000/ to view the project in action. Ensure to follow the project's coding standards and commit to the version control best practices for a consistent and professional codebase.

**note: Request the .env file from a fellow developer and place it at the root of the project directory. This file contains essential environment variables and configuration settings.**

### API Interaction and Documentation

For a detailed exploration of the API endpoints, developers can utilize tools like Postman or Swagger. These tools provide a user-friendly interface to send requests to the API, view responses, and understand the structure of the API in detail.

- **Postman**: An API client that allows you to create, share, test, and document APIs. You can import the collection of endpoints and start interacting with the API immediately.

- **Swagger**: Offers a web-based UI that renders Swagger-compliant APIs. If the project includes a Swagger schema, you can navigate to the API documentation URL (typically `/swagger/`) to see a list of endpoints, models, and try out the API directly in the browser.

Both of these tools are instrumental in developing, testing, and documenting RESTful services and will provide comprehensive insights into the API's capabilities.
