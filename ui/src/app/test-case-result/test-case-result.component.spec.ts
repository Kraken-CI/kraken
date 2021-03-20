import { waitForAsync, ComponentFixture, TestBed } from '@angular/core/testing'

import { TestCaseResultComponent } from './test-case-result.component'

describe('TestCaseResultComponent', () => {
    let component: TestCaseResultComponent
    let fixture: ComponentFixture<TestCaseResultComponent>

    beforeEach(
        waitForAsync(() => {
            TestBed.configureTestingModule({
                declarations: [TestCaseResultComponent],
            }).compileComponents()
        })
    )

    beforeEach(() => {
        fixture = TestBed.createComponent(TestCaseResultComponent)
        component = fixture.componentInstance
        fixture.detectChanges()
    })

    it('should create', () => {
        expect(component).toBeTruthy()
    })
})
