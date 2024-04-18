document.getElementById('openDataset').addEventListener('click', function () {
    var selectedValue = document.getElementById('field-linked_dataset').value;
    if (selectedValue) {
        var baseUrl = 'https://' + window.location.hostname; // Get the base URL
        var url = baseUrl + '/dataset/' + encodeURIComponent(selectedValue); // Construct the URL
        var win = window.open(url, '_blank');
        win.focus();
    } else {
        alert('Please select a dataset.');
        return;
    }
});
