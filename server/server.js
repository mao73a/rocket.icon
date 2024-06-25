const express = require('express');
const bodyParser = require('body-parser');
const fs = require('fs');
const path = require('path');
const app = express();
const port = 3000;

app.use(bodyParser.json());
app.use(bodyParser.urlencoded({ extended: true }));
app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views')); // Set the correct views directory
app.use(express.static(path.join(__dirname, 'public')));

// Endpoint to load the lists data
app.post('/load-lists', (req, res) => {
    const lists = {
        channels: req.body.channels.split(',').map(item => item.trim()),
        icons: req.body.icons.split(',').map(item => item.trim()),
        sounds: req.body.sounds.split(',').map(item => item.trim())
    };
    fs.writeFile(path.join(__dirname, 'data', 'lists.json'), JSON.stringify(lists, null, 2), 'utf8', (err) => {
        if (err) {
            return res.status(500).send({ message: 'Error saving lists' });
        }
        res.send({ message: 'Lists saved successfully' });
    });
});

// Endpoint to render the table editor
app.get('/edit/:filename', (req, res) => {
    const filename = req.params.filename;
    const tablePath = path.join(__dirname, 'data', `${filename}.json`);
    const listsPath = path.join(__dirname, 'data', 'lists.json');

    fs.readFile(tablePath, 'utf8', (err, tableData) => {
        if (err) {
            return res.status(500).send({ message: 'Table file not found' });
        }

        fs.readFile(listsPath, 'utf8', (err, listsData) => {
            if (err) {
                return res.status(500).send({ message: 'Lists file not found' });
            }

            res.render('edit', {
                table: JSON.parse(tableData),
                lists: JSON.parse(listsData),
            });
        });
    });
});

// Endpoint to save the edited table
app.post('/save-table', (req, res) => {
    const { filename, rules } = req.body;
    const data = { filename, rules };
    const tablePath = path.join(__dirname, 'data', `${filename}.json`);

    fs.writeFile(tablePath, JSON.stringify(data, null, 2), 'utf8', (err) => {
        if (err) {
            return res.status(500).send({ message: 'Error saving table' });
        }
        res.send({ message: 'Table saved successfully' });
    });
});

app.listen(port, () => {
    console.log(`Server running at http://localhost:${port}`);
});
