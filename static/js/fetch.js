   let url = "{% url 'campaign_list' %}"
   const request = new Request(url, {method: 'GET', body: formData});
   fetch(request)
      .then(response => response.json())
      .then(result => {
         console.log(result)
      })