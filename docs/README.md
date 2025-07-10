# VOLTS Documentation Site

This directory contains the GitHub Pages site for VOLTS (VoIP Open Linear Tester Suite).

## Local Development

To run the site locally:

1. Install Ruby and Bundler
2. Install dependencies:
   ```bash
   bundle install
   ```
3. Serve the site:
   ```bash
   bundle exec jekyll serve
   ```
4. Open http://localhost:4000

## Site Structure

- `_config.yml` - Jekyll configuration
- `_layouts/` - Page templates
- `_includes/` - Reusable components
- `assets/` - CSS, JS, and other assets
- `images/` - Images and graphics
- `index.md` - Main documentation content

## Updating Content

The main documentation content is in `index.md`. This file is generated from the main README.md but can be edited independently.

To update the navigation, modify the `navigation` section in `_config.yml`.

## Deployment

The site is automatically deployed to GitHub Pages when changes are pushed to the main branch. The site is available at the URL specified in `CNAME`.

## Customization

The site uses a custom design based on the original VOLTS documentation styling, with:
- Orange/teal color scheme
- Montserrat font
- Fixed sidebar navigation
- Responsive design
- Syntax highlighting for code blocks

CSS customizations are in `assets/css/style.scss`.