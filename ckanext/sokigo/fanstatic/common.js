// Below code is used for opening the dataset from Goto button in dataset. Thsi will open the dataset into new window.

 document.addEventListener('DOMContentLoaded', function () {
	 var openDatasetButton = document.getElementById('openDataset');
if (openDatasetButton) {
    openDatasetButton.addEventListener('click', function () {
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
} 
 });

// Below code is used for Publisher_Data.html file, when publisher is selected from drop down then show other read-only fields

 document.addEventListener('DOMContentLoaded', function () {
    var dropdown = document.getElementById('field-publisher_name');
    if(dropdown)
    {
    var uriField = document.getElementById('field-publisher_uri');
    var emailField = document.getElementById('field-publisher_email');
    var typeField = document.getElementById('field-publisher_type');
    var urlField = document.getElementById('field-publisher_url');

    function updateFields() {
        var selectedOption = dropdown.options[dropdown.selectedIndex];
        if (selectedOption.value) {
            uriField.value = selectedOption.getAttribute('data-uri');
            emailField.value = selectedOption.getAttribute('data-email');
            typeField.value = selectedOption.getAttribute('data-type');
            urlField.value = selectedOption.getAttribute('data-url');
        } else {
            uriField.value = '';
            emailField.value = '';
            typeField.value = '';
            urlField.value = '';
        }
    }

    dropdown.addEventListener('change', updateFields);

    // Trigger the change event to set initial values
    updateFields();
}
});		

// Below code is used for Publisher_Data.html file, when publisher is selected from drop down then show other read-only fields

 document.addEventListener('DOMContentLoaded', function () {
    var dropdown = document.getElementById('field-contact_name');
	if (dropdown) {
    var uriField = document.getElementById('field-contact_uri');
    var emailField = document.getElementById('field-contact_email');
    var typeField = document.getElementById('field-contact_type');
    var urlField = document.getElementById('field-contact_url');

    function updateFields() {
        var selectedOption = dropdown.options[dropdown.selectedIndex];
        if (selectedOption.value) {
            uriField.value = selectedOption.getAttribute('data-uri');
            emailField.value = selectedOption.getAttribute('data-email');
            typeField.value = selectedOption.getAttribute('data-type');
            urlField.value = selectedOption.getAttribute('data-url');
        } else {
            uriField.value = '';
            emailField.value = '';
            typeField.value = '';
            urlField.value = '';
        }
    }

    dropdown.addEventListener('change', updateFields);

    // Trigger the change event to set initial values
    updateFields();
	}
});		

// Below code is used for Creator_Data.html file, when creator is selected from drop down then show other read-only fields

 document.addEventListener('DOMContentLoaded', function () {
    var dropdown = document.getElementById('field-creator_name');
	if (dropdown) {
    var uriField = document.getElementById('field-creator_uri');
    var emailField = document.getElementById('field-creator_email');
    var typeField = document.getElementById('field-creator_type');
    var urlField = document.getElementById('field-creator_url');

    function updateFields() {
        var selectedOption = dropdown.options[dropdown.selectedIndex];
        if (selectedOption.value) {
            uriField.value = selectedOption.getAttribute('data-uri');
            emailField.value = selectedOption.getAttribute('data-email');
            typeField.value = selectedOption.getAttribute('data-type');
            urlField.value = selectedOption.getAttribute('data-url');
        } else {
            uriField.value = '';
            emailField.value = '';
            typeField.value = '';
            urlField.value = '';
        }
    }

    dropdown.addEventListener('change', updateFields);

    // Trigger the change event to set initial values
    updateFields();
	}
});		


//Generate GUId Button click on package_form.html in scheming plugin for generating GUId and assigning to last extra filed input box
document.addEventListener('DOMContentLoaded', function () {
  document.getElementById("generate-guid-btn").addEventListener("click", function() {

    // Generate a new GUID
      function generateGUID() {
          return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
              var r = Math.random() * 16 | 0, v = c === 'x' ? r : (c === 'y' ? (r & 0x3 | 0x8) : r);
              return v.toString(16);
          });
      }

      let newGUID = generateGUID();

      spanGUID = document.getElementById('span_GUID')
      spanGUID.textContent  = newGUID; 
  });
});
