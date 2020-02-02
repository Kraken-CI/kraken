import { async, ComponentFixture, TestBed } from '@angular/core/testing'

import { DiscoveredPageComponent } from './discovered-page.component'

describe('DiscoveredPageComponent', () => {
    let component: DiscoveredPageComponent
    let fixture: ComponentFixture<DiscoveredPageComponent>

    beforeEach(async(() => {
        TestBed.configureTestingModule({
            declarations: [DiscoveredPageComponent],
        }).compileComponents()
    }))

    beforeEach(() => {
        fixture = TestBed.createComponent(DiscoveredPageComponent)
        component = fixture.componentInstance
        fixture.detectChanges()
    })

    it('should create', () => {
        expect(component).toBeTruthy()
    })
})
